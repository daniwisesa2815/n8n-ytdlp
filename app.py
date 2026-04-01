import os
import uuid
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

    # Pakai unique ID agar tidak conflict saat concurrent requests
    uid = str(uuid.uuid4())[:8]
    input_file = f'/tmp/input_{uid}.mp4'
    output_file = f'/tmp/output_{uid}.mp4'

    try:
        download_cmd = [
    'yt-dlp',
    '--no-playlist',
    '--format', 'best[ext=mp4]/best',
    '--download-sections', f'*{start}-{end}',
    '--force-keyframes-at-cuts',
    '--extractor-args', 'youtube:player_client=ios',
    '--add-header', 'User-Agent:com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X)',
    '-o', input_file,
    youtube_url
]
        result = subprocess.run(download_cmd, check=True, timeout=300, capture_output=True, text=True)

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Download timeout'}), 408
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'Download failed: {e.stderr}'}), 500

    try:
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
        subprocess.run(ffmpeg_cmd, check=True, timeout=300, capture_output=True)

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Processing timeout'}), 408
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'FFmpeg failed: {e.stderr.decode()}'}), 500

    try:
        with open(output_file, 'rb') as f:
            response = requests.post(
                'https://file.io',
                files={'file': f},
                data={'expires': '1d'},
                timeout=60
            )
        result = response.json()
        download_url = result.get('link')
        if not download_url:
            return jsonify({'error': 'Upload to file.io failed', 'detail': result}), 500

    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    finally:
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
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
