import os
import uuid
import cv2
import numpy as np
from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
from flask_socketio import SocketIO
from moviepy.editor import VideoFileClip, ImageSequenceClip
import imageio
import shutil

app = Flask(__name__, static_folder='static')
socketio = SocketIO(app)

UPLOAD_FOLDER = 'upload'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def convert_to_grayscale(img, percentage):
    gray_img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray_img = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2RGB)
    blended_img = cv2.addWeighted(img, 1 - percentage, gray_img, percentage, 0)
    return blended_img

def apply_sepia(img, percentage):
    sepia_filter = np.array([[0.393 + 0.607 * (1 - percentage), 0.769 - 0.769 * (1 - percentage), 0.189 - 0.189 * (1 - percentage)],
                             [0.349 - 0.349 * (1 - percentage), 0.686 + 0.314 * (1 - percentage), 0.168 - 0.168 * (1 - percentage)],
                             [0.272 - 0.272 * (1 - percentage), 0.534 - 0.534 * (1 - percentage), 0.131 + 0.869 * (1 - percentage)]])
    sepia_img = cv2.transform(img, sepia_filter)
    sepia_img = np.clip(sepia_img, 0, 255).astype(np.uint8)
    return sepia_img

def invert_colors(img, percentage):
    inverted_img = cv2.bitwise_not(img)
    return cv2.addWeighted(img, 1 - percentage, inverted_img, percentage, 0)

def apply_blur(img, percentage):
    ksize = int(15 * percentage)
    if ksize % 2 == 0:
        ksize += 1
    blurred_img = cv2.GaussianBlur(img, (ksize, ksize), 0)
    return blurred_img

def increase_contrast(img, percentage):
    lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab_img)
    clahe = cv2.createCLAHE(clipLimit=3.0 * percentage, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab_img = cv2.merge((l, a, b))
    contrast_img = cv2.cvtColor(lab_img, cv2.COLOR_LAB2BGR)
    return contrast_img

def reduce_noise(img, percentage):
    h = 10 * percentage
    denoised_img = cv2.fastNlMeansDenoisingColored(img, None, h, h, 7, 21)
    return denoised_img

def detect_edges(img, percentage):
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if percentage == 0:
        return cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)

    low_threshold = int(100 * percentage)
    high_threshold = int(200 * percentage)
    
    edges_img = cv2.Canny(gray_img, low_threshold, high_threshold)
    return cv2.cvtColor(edges_img, cv2.COLOR_GRAY2BGR)

def apply_mosaic(img, percentage):
    size = max(1, int(10 * (1 - percentage)))
    small_img = cv2.resize(img, None, fx=1.0/size, fy=1.0/size, interpolation=cv2.INTER_AREA)
    return cv2.resize(small_img, img.shape[:2][::-1], interpolation=cv2.INTER_NEAREST)

def apply_wave_distortion(img, percentage):
    rows, cols = img.shape[:2]
    map_x = np.zeros((rows, cols), dtype=np.float32)
    map_y = np.zeros((rows, cols), dtype=np.float32)
    for i in range(rows):
        for j in range(cols):
            map_x[i, j] = int(j + 20 * percentage * np.sin(2 * np.pi * i / 180))
            map_y[i, j] = int(i + 20 * percentage * np.sin(2 * np.pi * j / 180))
    wave_distorted_img = cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LINEAR)
    return wave_distorted_img

def apply_mirror_effect(img, horizontal=True, percentage=None):
    if horizontal:
        return cv2.flip(img, 1)
    else:
        return cv2.flip(img, 0)

def apply_rotation(img, angle, percentage=None):
    rows, cols = img.shape[:2]
    M = cv2.getRotationMatrix2D((cols/2, rows/2), angle, 1)
    rotated_img = cv2.warpAffine(img, M, (cols, rows))
    return rotated_img

def apply_water_reflection(img, percentage):
    reflection_img = cv2.flip(img, 0)
    alpha = percentage
    beta = (1.0 - alpha)
    reflected_water_img = cv2.addWeighted(img, alpha, reflection_img, beta, 0.0)
    return reflected_water_img

@app.route('/')
def index():
    gif_files = []
    static_folder = app.static_folder
    
    for root, dirs, files in os.walk(static_folder):
        for file in files:
            if file.endswith(('.gif', '.mp4', '.webm')):
                file_path = os.path.relpath(os.path.join(root, file), static_folder)
                file_path = file_path.replace('\\', '/')  # Asegura que las barras estén correctas para URL
                gif_files.append(file_path)
                
    return render_template('index.html', gif_files=gif_files)

@app.route('/create_gif', methods=['POST'])
def create_gif():
    duration = float(request.form['duration'])
    start = float(request.form['start'])
    end = float(request.form['end'])
    fps = int(request.form['fps'])
    selected_effect = request.form['effect']
    percentage = float(request.form['percent']) / 100.0
    export_format = request.form['exportFormat']

    files = request.files.getlist('fileInput')
    alert_message = ''

    if files:
        random_code = str(uuid.uuid4())[:4]  # Nuevo: Generar código aleatorio para subcarpetas de usuario
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], f'usuario{random_code}')  # Nuevo: Crear subcarpeta en 'upload'
        static_user_folder = os.path.join(app.root_path, 'static', f'usuario{random_code}')  # Nuevo: Crear subcarpeta en 'static'
        os.makedirs(user_folder, exist_ok=True)
        os.makedirs(static_user_folder, exist_ok=True)

        for file in files:
            if file.filename.endswith(('.mp4', '.avi', '.mov', '.webp', '.gif')):
                random_filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
                video_path = os.path.join(user_folder, random_filename)  # Nuevo: Guardar en subcarpeta de usuario
                file.save(video_path)

                if start > 0 or end > 0:
                    video = VideoFileClip(video_path).subclip(start, end)
                    segment_duration = end - start
                else:
                    video = VideoFileClip(video_path)
                    segment_duration = video.duration

                if selected_effect != 'none':
                    if selected_effect == 'grayscale':
                        video = video.fl_image(lambda img: convert_to_grayscale(img, percentage))
                    elif selected_effect == 'sepia':
                        video = video.fl_image(lambda img: apply_sepia(img, percentage))
                    elif selected_effect == 'invert_colors':
                        video = video.fl_image(lambda img: invert_colors(img, percentage))
                    elif selected_effect == 'blur':
                        video = video.fl_image(lambda img: apply_blur(img, percentage))
                    elif selected_effect == 'contrast':
                        video = video.fl_image(lambda img: increase_contrast(img, percentage))
                    elif selected_effect == 'noise_reduction':
                        video = video.fl_image(lambda img: reduce_noise(img, percentage))
                    elif selected_effect == 'edge_detection':
                        video = video.fl_image(lambda img: detect_edges(img, percentage))
                    elif selected_effect == 'mosaic':
                        video = video.fl_image(lambda img: apply_mosaic(img, percentage))
                    elif selected_effect == 'wave_distortion':
                        video = video.fl_image(lambda img: apply_wave_distortion(img, percentage))
                    elif selected_effect == 'mirror_horizontal':
                        video = video.fl_image(lambda img: apply_mirror_effect(img, horizontal=True, percentage=percentage))
                    elif selected_effect == 'mirror_vertical':
                        video = video.fl_image(lambda img: apply_mirror_effect(img, horizontal=False, percentage=percentage))
                    elif selected_effect == 'rotate':
                        video = video.fl_image(lambda img: apply_rotation(img, angle=90, percentage=percentage))
                    elif selected_effect == 'water_reflection':
                        video = video.fl_image(lambda img: apply_water_reflection(img, percentage))

                gif_fps = fps / segment_duration if segment_duration > 0 else 1

                output_filename = str(uuid.uuid4()) + '.' + export_format
                output_path = os.path.join(static_user_folder, output_filename)  # Nuevo: Guardar en subcarpeta de usuario

                if export_format == 'gif':
                    video.write_gif(output_path, fps=gif_fps)
                elif export_format == 'mp4':
                    video.write_videofile(output_path, fps=fps)
                elif export_format == 'webm':
                    video.write_videofile(output_path, codec='libvpx', fps=fps)
                
                video.close()
                os.remove(video_path)
                alert_message = '¡El archivo de video se ha cargado y procesado correctamente!'
                return alert_message

            elif file.filename.endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                frames = []
                img = cv2.imdecode(np.frombuffer(file.read(), np.uint8), -1)

                if selected_effect != 'none':
                    if selected_effect == 'grayscale':
                        img = convert_to_grayscale(img, percentage)
                    elif selected_effect == 'sepia':
                        img = apply_sepia(img, percentage)
                    elif selected_effect == 'invert_colors':
                        img = invert_colors(img, percentage)
                    elif selected_effect == 'blur':
                        img = apply_blur(img, percentage)
                    elif selected_effect == 'contrast':
                        img = increase_contrast(img, percentage)
                    elif selected_effect == 'noise_reduction':
                        img = reduce_noise(img, percentage)
                    elif selected_effect == 'edge_detection':
                        img = detect_edges(img, percentage)
                    elif selected_effect == 'mosaic':
                        img = apply_mosaic(img, percentage)
                    elif selected_effect == 'wave_distortion':
                        img = apply_wave_distortion(img, percentage)
                    elif selected_effect == 'mirror_horizontal':
                        img = apply_mirror_effect(img, horizontal=True, percentage=percentage)
                    elif selected_effect == 'mirror_vertical':
                        img = apply_mirror_effect(img, horizontal=False, percentage=percentage)
                    elif selected_effect == 'rotate':
                        img = apply_rotation(img, angle=90, percentage=percentage)
                    elif selected_effect == 'water_reflection':
                        img = apply_water_reflection(img, percentage)

                frames.append(img)
                
                if frames:
                    output_filename = str(uuid.uuid4()) + '.' + export_format
                    output_path = os.path.join(static_user_folder, output_filename)  # Nuevo: Guardar en subcarpeta de usuario

                    if export_format == 'gif':
                        imageio.mimsave(output_path, frames, format='GIF', fps=fps)
                    elif export_format == 'mp4':
                        clip = ImageSequenceClip(frames, fps=fps)
                        clip.write_videofile(output_path, codec='libx264')
                    elif export_format == 'webm':
                        clip = ImageSequenceClip(frames, fps=fps)
                        clip.write_videofile(output_path, codec='libvpx')

                    alert_message = '¡El archivo de imagen se ha cargado y procesado correctamente!'
                    return send_file(output_path, as_attachment=True, download_name=output_filename)
                
            else:
                alert_message = '¡No se encontraron archivos válidos para procesar!'
    else:
        alert_message = '¡No brindaste ningún archivo!'

    return alert_message

@app.route('/download_file/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory('static', filename)

@app.route('/get_files', methods=['GET'])
def get_files():
    static_folder = 'static'
    files = []
    for root, dirs, file_list in os.walk(static_folder):
        for file in file_list:
            if file.endswith(('.gif', '.mp4', '.webp')):
                files.append(os.path.relpath(os.path.join(root, file), static_folder))

    if not files:
        return jsonify({'status': 'error', 'message': '¡No se encontraron archivos válidos para procesar!'})
    return jsonify({'status': 'success', 'files': files})

@app.route('/delete_files', methods=['POST'])
def delete_files():
    static_folder = 'static'
    try:
        for folder_name in os.listdir(static_folder):
            folder_path = os.path.join(static_folder, folder_name)
            if os.path.isdir(folder_path):
                for file_name in os.listdir(folder_path):
                    if file_name.endswith(('.gif', '.mp4', '.webp')):
                        os.remove(os.path.join(folder_path, file_name))
                os.rmdir(folder_path)  # Elimina la subcarpeta de usuario
        return jsonify({'status': 'success', 'message': 'Todos los archivos y subcarpetas se han eliminado con éxito.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error al eliminar archivos: {str(e)}'})


if __name__ == '__main__':
    socketio.run(app, debug=True)
