# writing_tool/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from research_assistant.extensions import db,get_s3_client
from research_assistant.writing_tool.models import Document, DocumentVersion
from research_assistant.user.models import User
from research_assistant.utils import upload_file_to_s3


writing_tool_bp = Blueprint("writing_tool", __name__, url_prefix="/writing_tool")

@writing_tool_bp.route("/documents", methods=["POST"])
@jwt_required()
def create_document():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    title = request.form.get("title")
    file = request.files.get("file")

    if not title or not file:
        return jsonify({"code": 1, "msg": "Missing title or file"}), 400

    document = Document(title=title)
    db.session.add(document)
    db.session.flush()

    file_key = f"documents/{document.id}_v1.0_{file.filename}"

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    file_size = round(size / (1024 * 1024), 2)

    file_url = upload_file_to_s3(file, file_key)

    version = DocumentVersion(
        document_id=document.id,
        major_version=1,
        minor_version=0,
        file_key=file_key,
        file_url=file_url,
        uploaded_by_id=user.id,
        file_size=file_size,
        is_current=True
    )

    db.session.add(version)
    db.session.commit()

    return jsonify({"code": 0, "msg": "Document created", "document_id": document.id})



@writing_tool_bp.route("/documents", methods=["GET"])
@jwt_required()
def list_documents_with_all_versions():
    """Get all documents including all versions info."""
    documents = Document.query.all()
    result = []
    for doc in documents:
        version_list = []
        for v in DocumentVersion.query.filter_by(document_id=doc.id).order_by(DocumentVersion.uploaded_at.desc()).all():
            version_list.append({
                "version_id": v.id,
                "version": f"v{v.major_version}.{v.minor_version}",
                "uploaded_at": v.uploaded_at.isoformat(),
                "file_size": v.file_size,
                "is_current": v.is_current,
                "file_url": v.file_url
            })
        result.append({
            "document_id": doc.id,
            "title": doc.title,
            "created_at": doc.created_at.isoformat() if hasattr(doc, 'created_at') else None,
            "versions": version_list
        })
    return jsonify({"code": 0, "data": result})



@writing_tool_bp.route("/documents/<string:document_id>/versions", methods=["POST"])
@jwt_required()
def upload_new_version(document_id):
    user_id = get_jwt_identity()
    file = request.files.get("file")

    if not file:
        return jsonify({"code": 1, "msg": "Missing file"}), 400

    document = Document.query.get_or_404(document_id)

    latest = DocumentVersion.query.filter_by(document_id=document_id)\
        .order_by(DocumentVersion.major_version.desc(), DocumentVersion.minor_version.desc())\
        .first()

    if latest:
        major = latest.major_version
        minor = latest.minor_version + 1
        if minor >= 10:
            major += 1
            minor = 0
        latest.is_current = False
    else:
        major, minor = 1, 0

    new_version_str = f"v{major}.{minor}"
    file_key = f"documents/{document.id}_{new_version_str}_{file.filename}"

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    file_size = round(size / (1024 * 1024), 2)

    file_url = upload_file_to_s3(file, file_key)

    version = DocumentVersion(
        document_id=document.id,
        major_version=major,
        minor_version=minor,
        file_key=file_key,
        file_url=file_url,
        uploaded_by_id=user_id,
        file_size=file_size,
        is_current=True
    )

    db.session.add(version)
    db.session.commit()

    return jsonify({"code": 0, "msg": "New version uploaded", "version": new_version_str})



@writing_tool_bp.route("/documents/<string:document_id>/versions/<string:version_id>/download", methods=["GET"])
@jwt_required()
def download_version(document_id, version_id):
    """Return presigned URL for downloading a specific version."""
    user_id = int(get_jwt_identity())

    try:
        major, minor = map(int, version_id.lstrip('v').split('.'))
    except Exception:
        return jsonify({"code": 1, "msg": "Invalid version_id format"}), 400

    version = DocumentVersion.query.filter_by(
        document_id=document_id,
        major_version=major,
        minor_version=minor
    ).first_or_404()

    if version.uploaded_by_id != user_id:
        return jsonify({"code": 1, "msg": "Unauthorized access"}), 403

    try:
        s3_client = get_s3_client()
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': '9900-files', 'Key': version.file_key},
            ExpiresIn=3600
        )
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Failed to generate download link: {str(e)}"}), 500

    return jsonify({"code": 0, "file_url": presigned_url})


@writing_tool_bp.route("/documents/<string:document_id>/versions/<string:version_id>", methods=["DELETE"])
@jwt_required()
def delete_version(document_id, version_id):
    """Delete a specific version and its file in S3."""
    try:
        major, minor = map(int, version_id.lstrip('v').split('.'))
    except Exception:
        return jsonify({"code": 1, "msg": "Invalid version_id format"}), 400

    version = DocumentVersion.query.filter_by(
        document_id=document_id,
        major_version=major,
        minor_version=minor
    ).first_or_404()
    s3_client = get_s3_client()
    try:
        s3_client.delete_object(Bucket="9900-files", Key=version.file_key)
    except Exception as e:
        return jsonify({"code": 1, "msg": f"Failed to delete file from S3: {str(e)}"}), 500

    db.session.delete(version)
    db.session.commit()

    return jsonify({"code": 0, "msg": "Version and file deleted"})


@writing_tool_bp.route("/documents/<string:document_id>", methods=["DELETE"])
@jwt_required()
def delete_document(document_id):
    """Delete an entire document, all its versions, and all related files in S3."""
    document = Document.query.get_or_404(document_id)
    s3_client = get_s3_client()
    for version in document.versions:
        try:
            s3_client.delete_object(Bucket="9900-files", Key=version.file_key)
        except Exception as e:
            return jsonify({"code": 1, "msg": f"Failed to delete file {version.file_key} from S3: {str(e)}"}), 500
        db.session.delete(version)

    db.session.delete(document)
    db.session.commit()

    return jsonify({"code": 0, "msg": "Document and all files deleted"}) 