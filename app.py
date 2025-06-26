from flask import Flask, render_template, request, send_file, session, redirect, url_for
from rembg import remove, new_session
from PIL import Image
import io
import os
import time
from threading import Thread
from functools import wraps
from flask import send_from_directory

app = Flask(__name__)
app.secret_key = 'secret_key'  # Ganti dengan kunci rahasia yang kuat
UPLOAD_FOLDER = 'static'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
INACTIVE_THRESHOLD = 60  # Hapus file setelah 60 detik tidak aktif

# Login user sederhana
users = {'user': 'password'}

# Untuk tracking file yang akan dihapus otomatis
last_access_time = {}

# Model rembg paling akurat
session_rembg = new_session(model_name='isnet-general-use')

# Cek ekstensi file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Resize gambar kecil agar model bisa memproses lebih baik
def preprocess_image(image):
    MIN_SIZE = 512
    width, height = image.size
    if width < MIN_SIZE or height < MIN_SIZE:
        ratio = MIN_SIZE / float(min(width, height))
        new_size = (int(width * ratio), int(height * ratio))
        image = image.resize(new_size, Image.LANCZOS)
    return image

# Auto delete file setelah tidak digunakan
def cleanup_inactive_files():
    while True:
        time.sleep(10)
        now = time.time()
        files_to_delete = []
        for filename, last_access in list(last_access_time.items()):
            if now - last_access > INACTIVE_THRESHOLD:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(filepath):
                    try:
                        os.unlink(filepath)
                        print(f"File otomatis dihapus: {filename}")
                        files_to_delete.append(filename)
                    except Exception as e:
                        print(f"Gagal menghapus {filename}: {e}")
        for filename in files_to_delete:
            last_access_time.pop(filename, None)

# Mulai thread auto-cleanup
cleanup_thread = Thread(target=cleanup_inactive_files)
cleanup_thread.daemon = True
cleanup_thread.start()

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username] == password:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Username atau password salah')
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

# Middleware login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Halaman utama
@app.route('/', methods=['GET', 'POST'])
def index():
    result_filename = session.get('result_filename')
    if request.method == 'POST':
        image_file = request.files['image']
        if image_file and allowed_file(image_file.filename):
            filename = 'result.png'
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Proses gambar
            input_image = Image.open(image_file.stream).convert("RGBA")
            input_image = preprocess_image(input_image)
            output_image = remove(input_image, session=session_rembg)

            # Simpan hasil
            output_image.save(filepath, format="PNG", optimize=True)
            session['result_filename'] = filename
            last_access_time[filename] = time.time()

            return render_template('index.html', result=True, logged_in=session.get('logged_in'), result_filename=filename)

    return render_template('index.html', result=False, logged_in=session.get('logged_in'), result_filename=result_filename)

# Download normal
@app.route('/download')
def download_normal():
    filename = session.get('result_filename')
    if filename and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        last_access_time[filename] = time.time()
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)
    return "File tidak ditemukan.", 404

# Download versi HD (hanya untuk user login)
@app.route('/download/hd')
@login_required
def download_hd():
    filename = session.get('result_filename')
    if filename and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        last_access_time[filename] = time.time()
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True, mimetype='image/png', download_name='result_hd.png')
    return "File tidak ditemukan HD.", 404

# Hapus gambar secara manual
@app.route('/hapus_gambar', methods=['POST'])
def hapus_gambar():
    filename = session.get('result_filename')
    if filename and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        try:
            os.unlink(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            session.pop('result_filename', None)
            last_access_time.pop(filename, None)
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Gagal menghapus {filename}: {e}")
            return "Gagal menghapus gambar.", 500
    return redirect(url_for('index'))


# Tambahan halaman
@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/panduan')
def panduan():
    return render_template('panduan.html')

@app.route('/syarat')
def syarat():
    return render_template('syarat.html')

@app.route('/privasi')
def privasi():
    return render_template('privasi.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/sitemap.xml')
def sitemap_xml():
    return send_from_directory('.', 'sitemap.xml')

@app.route('/robots.txt')
def robots_txt():
    return send_from_directory('.', 'robots.txt')


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    print("Server ready... http://localhost:5000")
    app.run(debug=True)
