# Marketing\app\mail\routes.py

from app.mail import bp
from app.models import MailUser, Agency
from app.utils import login_required
from app.database import db
from flask import render_template, request, session, flash, redirect, url_for, Response
from imap_tools import MailBox, A

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
            domain = "imap.gmail.com"
        elif server == "outlook":
            folder = "Sent"
            domain = "imap-mail.outlook.com"
        elif server == "t-online":
            folder = "INBOX.Sent"
            domain = "secureimap.t-online.de"
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

    users = db.session.execute(db.select(MailUser).where(
        MailUser.agency_id == currentAgency.get("id")
        )).scalars()
    return render_template("mail_main.html", users=users)

@bp.route("/get-mails")
def get_mail():
    existingUser = db.get_or_404(MailUser, request.args.get("user_id"))
    mails = []
    with MailBox(existingUser.domain).login(existingUser.email, existingUser.password) as mb:
        mb.folder.set(existingUser.folder)
        mails = list(mb.fetch(limit=30))

    return render_template(
            "show_mail.html",
            mails=mails,
            user_id=existingUser.id
            )

@bp.route("/check-email")
def check_mail():
    email = request.args.get("email")
    password = request.args.get("password")
    server = request.args.get("server")
    try:
        if server == "gmail":
            mb = MailBox("imap.gmail.com")
            mb.login(email, password, "[Gmail]/Sent Mail")
        elif server == "outlook":
            mb = MailBox("imap-mail.outlook.com")
            mb.login(email, password, "Sent")
        elif server == "t-online":
            mb = MailBox("secureimap.t-online.de")
            mb.login(email, password, "INBOX.Sent")
    except Exception:
        return "<h4>Could not login, incorrect email/password.</h4>"
    finally:
        mb.logout()
    return render_template("mail_submit.html")

@bp.route("/mail-att/<user_id>/<mail_id>/<filename>")
def get_att(user_id, mail_id, filename):
    existingUser = db.get_or_404(MailUser, user_id)
    with MailBox(existingUser.domain).login(existingUser.email, existingUser.password) as mb:
        mb.folder.set(existingUser.folder)
        mail = list(mb.fetch(A(uid=mail_id)))[0]

    for att in mail.attachments:
        if att.filename == filename:
            res = Response(att.payload)
            res.headers["Content-Disposition"] = f'attachment; filename="{att.filename}"'
            res.headers["filename"] = att.filename
            res.headers["content-type"] = att.content_type
            return res

