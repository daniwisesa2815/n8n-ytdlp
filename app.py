import os
import subprocess
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/clip', methods=['POST'])
def clip():
    data = request.json
    youtube_url = data.get('youtube_url')
    start = int(data.get('start', 0))
    end = int(data.get('end', 30))

    if not youtube_url:
        return jsonify({'error': 'youtube_url required'}), 400

    duration = end - start
    input_file = '/tmp/input.mp4'
    output_file = '/tmp/output.mp4'

    # Hapus file lama kalau ada
    for f in [input_file, output_file]:
        if os.path.exists(f):
            os.remove(f)

    try:
        # Download video pakai yt-dlp dengan antisipasi block YouTube
        download_cmd = [
            'yt-dlp',
            '--no-playlist',
            '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--download-sections', f'*{start}-{end}',
            '--force-keyframes-at-cuts',
            '--add-header', 'User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '-o', input_file,
            youtube_url
        ]
        subprocess.run(download_cmd, check=True, timeout=300)

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Download timeout - video too long'}), 408
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'Download failed: {str(e)}'}), 500

    try:
        # Reframe ke 9:16 pakai ffmpeg
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', input_file,
            '-t', str(duration),
            '-vf', 'crop=ih*9/16:ih,scale=1080:1920',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-c:a', 'aac',
            output_file
        ]
        subprocess.run(ffmpeg_cmd, check=True, timeout=300)

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Processing timeout'}), 408
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'FFmpeg failed: {str(e)}'}), 500

    try:
        # Upload ke file.io (free, no account needed, file auto-delete setelah 1x download)
        with open(output_file, 'rb') as f:
            response = requests.post(
                'https://file.io',
                files={'file': f},
                data={'expires': '1d'}
            )
        result = response.json()
        download_url = result.get('link')

        if not download_url:
            return jsonify({'error': 'Upload failed'}), 500

    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    finally:
        # Selalu hapus file lokal
        for f in [input_file, output_file]:
            if os.path.exists(f):
                os.remove(f)

    return jsonify({
        'success': True,
        'download_url': download_url,
        'start': start,
        'end': end,
        'duration': duration
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
