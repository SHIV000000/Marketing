# app/mail/routes.py

from app.mail import bp
from app.models import MailUser, Agency, Email
from app.utils import login_required
from app.database import db
from flask import render_template, request, session, flash, redirect, url_for, Response, jsonify
from app.mail.email_handler import EmailHandler

@bp.route("/", methods=["GET", "POST"])
@login_required
def main():
    currentAgency = session.get('currentAgency')
    agency = db.session.execute(db.select(Agency).where(Agency.id == currentAgency.get("id"))).scalar_one_or_none()
    if request.method == "POST":
        existingUser = db.session.execute(db.select(MailUser).where(
            MailUser.agency_id == currentAgency.get("id")).where(
            MailUser.email == request.form.get("email")
            )).scalar_one_or_none()

        if existingUser:
            flash("User is already added with this email", "danger")
            return redirect(url_for("mail.main"))

        server = request.form.get("server")
        if server == "gmail":
            folder = "[Gmail]/Sent Mail"
            domain = "gmail.com"
        elif server == "outlook":
            folder = "Sent"
            domain = "outlook.com"
        elif server == "t-online":
            folder = "INBOX.Sent"
            domain = "t-online.de"
        
        email_handler = EmailHandler()
        success, message = email_handler.check_email_connection(
            request.form.get("email"),
            request.form.get("password"),
            domain
        )
        
        if not success:
            flash(f"Failed to add email: {message}", "danger")
            return redirect(url_for("mail.main"))
        
        newUser = MailUser(
                email=request.form.get("email"),
                password=request.form.get("password"),
                domain=domain,
                folder=folder,
                agency_id=agency.id,
                agency=agency
                )
        db.session.add(newUser)
        db.session.commit()
        flash("Email account added successfully", "success")

    users = db.session.execute(db.select(MailUser).where(
        MailUser.agency_id == currentAgency.get("id")
        )).scalars()
    return render_template("mail_main.html", users=users)

@bp.route("/get-mails")
@login_required
def get_mail():
    existingUser = db.get_or_404(MailUser, request.args.get("user_id"))
    emails = Email.query.filter_by(mail_user_id=existingUser.id).order_by(Email.date.desc()).limit(30).all()
    return render_template(
            "show_mail.html",
            emails=emails,
            user_id=existingUser.id
            )

@bp.route("/check-email")
def check_mail():
    email = request.args.get("email")
    password = request.args.get("password")
    server = request.args.get("server")
    
    email_handler = EmailHandler()
    success, message = email_handler.check_email_connection(email, password, server)
    
    if success:
        return render_template("mail_submit.html")
    else:
        return f"<h4>{message}</h4>"

@bp.route("/mail-att/<int:user_id>/<int:email_id>/<filename>")
@login_required
def get_att(user_id, email_id, filename):
    email_handler = EmailHandler()
    attachments = email_handler.get_email_attachments(user_id, email_id)
    
    if attachments is None:
        flash("Failed to retrieve attachments", "danger")
        return redirect(url_for("mail.main"))
    
    for att in attachments:
        if att['filename'] == filename:
            res = Response(att['content'])
            res.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            res.headers["filename"] = filename
            res.headers["content-type"] = "application/octet-stream"
            return res
    
    flash("Attachment not found", "danger")
    return redirect(url_for("mail.main"))

@bp.route("/sync-emails")
@login_required
def sync_emails():
    currentAgency = session.get('currentAgency')
    email_handler = EmailHandler()
    try:
        email_handler.sync_emails(currentAgency.get("id"))
        flash("Emails synced successfully", "success")
    except Exception as e:
        flash(f"Error syncing emails: {str(e)}", "danger")
    return redirect(url_for("mail.main"))

@bp.route("/delete-email-account/<int:user_id>", methods=["POST"])
@login_required
def delete_email_account(user_id):
    mail_user = db.get_or_404(MailUser, user_id)
    if mail_user.agency_id != session.get('currentAgency').get("id"):
        flash("You don't have permission to delete this email account", "danger")
        return redirect(url_for("mail.main"))
    
    try:
        Email.query.filter_by(mail_user_id=user_id).delete()
        db.session.delete(mail_user)
        db.session.commit()
        flash("Email account deleted successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting email account: {str(e)}", "danger")
    
    return redirect(url_for("mail.main"))

@bp.route("/search-emails", methods=["GET", "POST"])
@login_required
def search_emails():
    if request.method == "POST":
        search_term = request.form.get("search_term")
        user_id = request.form.get("user_id")
        
        emails = Email.query.filter(
            Email.mail_user_id == user_id,
            (Email.subject.ilike(f"%{search_term}%") | Email.content.ilike(f"%{search_term}%"))
        ).order_by(Email.date.desc()).all()
        
        return render_template("search_results.html", emails=emails, user_id=user_id)
    
    users = MailUser.query.filter_by(agency_id=session.get('currentAgency').get("id")).all()
    return render_template("search_emails.html", users=users)

