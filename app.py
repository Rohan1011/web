\
import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# Load .env if present
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

def create_app():
    app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    sqlite_path = os.getenv("SQLITE_PATH", os.path.join(INSTANCE_DIR, "site.db"))
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{sqlite_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    return app

app = create_app()
db = SQLAlchemy(app)

# ---------- Models ----------
class Enquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(50))
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BusinessAsset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)  # store JSON/text

class GalleryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255))
    alt = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class NewsArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    image = db.Column(db.String(1000))
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ---------- Helpers ----------
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper

# ---------- Routes ----------
@app.route("/")
def index():
    latest_news = NewsArticle.query.order_by(NewsArticle.created_at.desc()).limit(6).all()
    return render_template("index.html", latest_news=latest_news)

@app.route("/business")
def business():
    hero_title = (BusinessAsset.query.filter_by(key="hero_title").first() or BusinessAsset(key="hero_title", value="Our Business")).value
    hero_sub = (BusinessAsset.query.filter_by(key="hero_subtitle").first() or BusinessAsset(key="hero_subtitle", value="We deliver value.")).value
    gallery = GalleryImage.query.order_by(GalleryImage.uploaded_at.desc()).all()
    return render_template("business.html", hero_title=hero_title, hero_subtitle=hero_sub, gallery=gallery)

@app.route("/news")
def news():
    articles = NewsArticle.query.order_by(NewsArticle.created_at.desc()).all()
    return render_template("news.html", articles=articles)

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip()
        phone = request.form.get("phone","").strip()
        message = request.form.get("message","").strip()
        if not name or not email or not message:
            flash("Name, email and message are required.", "error")
            return redirect(url_for("contact"))
        e = Enquiry(name=name, email=email, phone=phone, message=message)
        db.session.add(e)
        db.session.commit()
        flash("Thanks! We received your enquiry and will get back to you soon.", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password and password == os.getenv("ADMIN_PASSWORD", "admin"):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid password", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))

@app.route("/admin", methods=["GET"])
@admin_required
def admin_dashboard():
    enquiries_count = Enquiry.query.count()
    images_count = GalleryImage.query.count()
    news_count = NewsArticle.query.count()
    return render_template("admin_dashboard.html", enquiries_count=enquiries_count, images_count=images_count, news_count=news_count)

@app.route("/admin/business", methods=["GET", "POST"])
@admin_required
def admin_business():
    if request.method == "POST":
        # Update hero text
        hero_title = request.form.get("hero_title","").strip()
        hero_subtitle = request.form.get("hero_subtitle","").strip()
        for k, v in [("hero_title", hero_title), ("hero_subtitle", hero_subtitle)]:
            asset = BusinessAsset.query.filter_by(key=k).first()
            if not asset:
                asset = BusinessAsset(key=k, value=v)
                db.session.add(asset)
            else:
                asset.value = v
        # Handle image upload(s)
        if "image" in request.files:
            f = request.files["image"]
            if f and f.filename:
                fname = secure_filename(f.filename)
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], fname)
                f.save(save_path)
                img = GalleryImage(filename=fname, title=request.form.get("img_title"), alt=request.form.get("img_alt"))
                db.session.add(img)
        db.session.commit()
        flash("Business page updated.", "success")
        return redirect(url_for("admin_business"))
    hero_title = (BusinessAsset.query.filter_by(key="hero_title").first() or BusinessAsset(key="hero_title", value="Our Business")).value
    hero_sub = (BusinessAsset.query.filter_by(key="hero_subtitle").first() or BusinessAsset(key="hero_subtitle", value="We deliver value.")).value
    gallery = GalleryImage.query.order_by(GalleryImage.uploaded_at.desc()).all()
    return render_template("admin_business.html", hero_title=hero_title, hero_subtitle=hero_sub, gallery=gallery)

@app.route("/admin/enquiries")
@admin_required
def admin_enquiries():
    q = Enquiry.query.order_by(Enquiry.created_at.desc()).all()
    return render_template("admin_enquiries.html", enquiries=q)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), "uploads"), filename)

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
