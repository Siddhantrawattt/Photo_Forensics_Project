from flask import Flask, render_template, request, send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import os
import hashlib
import exifread
from PIL import Image, ImageChops, ImageEnhance, ImageStat

app = Flask(__name__)


def convert_to_decimal(value):
    d = float(value.values[0].num) / float(value.values[0].den)
    m = float(value.values[1].num) / float(value.values[1].den)
    s = float(value.values[2].num) / float(value.values[2].den)

    return d + (m / 60.0) + (s / 3600.0)


@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":

        photo = request.files["photo"]

        if photo:

            # =========================
            # SAVE PHOTO
            # =========================
            filepath = os.path.join("static", "uploads", photo.filename)
            photo.save(filepath)

            # =========================
            # ELA (Error Level Analysis)
            # =========================
            ela_path = os.path.join("static", "ela", photo.filename)
            temp_path = os.path.join("static", "ela", "temp.jpg")

            original = Image.open(filepath).convert("RGB")
            original.save(temp_path, "JPEG", quality=90)

            compressed = Image.open(temp_path)

            diff = ImageChops.difference(original, compressed)

            extrema = diff.getextrema()
            max_diff = max([ex[1] for ex in extrema])

            if max_diff == 0:
                max_diff = 1

            scale = 255.0 / max_diff

            ela_image = ImageEnhance.Brightness(diff).enhance(scale)
            ela_image.save(ela_path)

            # =========================
            # ELA SCORE
            # =========================
            stat = ImageStat.Stat(ela_image)

            ela_score = sum(stat.mean) / len(stat.mean)

            if ela_score < 15:
                ela_result = "✅ Image appears Genuine"
            elif ela_score < 30:
                ela_result = "⚠ Minor compression differences detected"
            else:
                ela_result = "🚨 Possible Image Manipulation Detected"

            # =========================
            # HASH VALUES
            # =========================
            with open(filepath, "rb") as f:
                data = f.read()

            md5_hash = hashlib.md5(data).hexdigest()
            sha256_hash = hashlib.sha256(data).hexdigest()

            # =========================
            # IMAGE DETAILS
            # =========================
            image = Image.open(filepath)

            width, height = image.size
            image_format = image.format
            file_size = round(os.path.getsize(filepath) / 1024, 2)

            # =========================
            # EXIF DETAILS
            # =========================
            with open(filepath, "rb") as f:
                tags = exifread.process_file(f)

            camera = tags.get("Image Model", "Not Found")
            date_taken = tags.get("EXIF DateTimeOriginal", "Not Found")

            gps_lat = "Not Found"
            gps_lon = "Not Found"
            maps_link = ""

            if "GPS GPSLatitude" in tags and "GPS GPSLongitude" in tags:

                lat = convert_to_decimal(tags["GPS GPSLatitude"])
                lon = convert_to_decimal(tags["GPS GPSLongitude"])

                gps_lat = round(lat, 6)
                gps_lon = round(lon, 6)

                maps_link = f"https://www.google.com/maps?q={gps_lat},{gps_lon}"

            # =========================
            # SAVE REPORT DATA
            # =========================
            app.config["report_data"] = {
                "filename": photo.filename,
                "camera": str(camera),
                "date_taken": str(date_taken),
                "width": width,
                "height": height,
                "image_format": image_format,
                "file_size": file_size,
                "gps_lat": gps_lat,
                "gps_lon": gps_lon,
                "md5_hash": md5_hash,
                "sha256_hash": sha256_hash,
                "ela_score": round(ela_score, 2),
                "ela_result": ela_result,
            }

            return render_template(
                "result.html",
                filepath=filepath,
                ela_path=ela_path,
                filename=photo.filename,
                camera=camera,
                date_taken=date_taken,
                width=width,
                height=height,
                image_format=image_format,
                file_size=file_size,
                gps_lat=gps_lat,
                gps_lon=gps_lon,
                maps_link=maps_link,
                md5_hash=md5_hash,
                sha256_hash=sha256_hash,
                ela_score=round(ela_score, 2),
                ela_result=ela_result,
            )

    return render_template("index.html")


@app.route("/download_pdf")
def download_pdf():

    report = app.config.get("report_data")

    if not report:
        return "No Report Found"

    pdf_file = "Photo_Forensics_Report.pdf"

    doc = SimpleDocTemplate(pdf_file)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>Digital Photo Forensics Report</b>", styles["Title"]))
    story.append(Paragraph("<br/>", styles["Normal"]))

    story.append(Paragraph(f"<b>Filename:</b> {report['filename']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Camera:</b> {report['camera']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Date Taken:</b> {report['date_taken']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Resolution:</b> {report['width']} x {report['height']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Image Format:</b> {report['image_format']}", styles["Normal"]))
    story.append(Paragraph(f"<b>File Size:</b> {report['file_size']} KB", styles["Normal"]))

    story.append(Paragraph("<br/>", styles["Normal"]))

    story.append(Paragraph(f"<b>GPS Latitude:</b> {report['gps_lat']}", styles["Normal"]))
    story.append(Paragraph(f"<b>GPS Longitude:</b> {report['gps_lon']}", styles["Normal"]))

    story.append(Paragraph("<br/>", styles["Normal"]))

    story.append(Paragraph(f"<b>MD5:</b> {report['md5_hash']}", styles["Normal"]))
    story.append(Paragraph(f"<b>SHA256:</b> {report['sha256_hash']}", styles["Normal"]))

    story.append(Paragraph("<br/>", styles["Normal"]))

    story.append(Paragraph(f"<b>ELA Score:</b> {report['ela_score']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Status:</b> {report['ela_result']}", styles["Normal"]))

    doc.build(story)

    return send_file(pdf_file, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)