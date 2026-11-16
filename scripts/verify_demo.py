"""Verify the recorded media and local-page autoplay with default browser policy."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess


async def verify(project):
    from PIL import Image
    from playwright.async_api import async_playwright

    assets = project / 'docs/assets'
    video = assets / 'demo.mp4'
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format',
        '-of', 'json', str(video)], text=True))
    stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    assert stream['codec_name'] == 'h264'
    assert stream['pix_fmt'] == 'yuv420p'
    assert float(probe['format']['duration']) > 10
    with Image.open(assets / 'demo.gif') as gif:
        gif_info = {'frames': gif.n_frames, 'loop': gif.info.get('loop'),
                    'width': gif.width, 'height': gif.height}
        assert gif_info['frames'] > 1 and gif_info['loop'] == 0

    errors = []
    async with async_playwright() as p:
        options = {'headless': True, 'timeout': 45000}
        chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        if not Path(p.chromium.executable_path).exists() and chrome.exists():
            options['executable_path'] = str(chrome)
        browser = await p.chromium.launch(**options)
        page = await browser.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto((project / 'docs/demo.html').resolve().as_uri())
        await page.wait_for_function('''() => {
            const v = document.querySelector('video');
            return v && !v.paused && v.currentTime > 0.5;
        }''', timeout=20000)
        state = await page.locator('video').evaluate('''v => ({
            paused: v.paused, currentTime: v.currentTime, muted: v.muted,
            autoplay: v.autoplay, loop: v.loop, playsInline: v.playsInline,
            readyState: v.readyState, error: v.error && v.error.message
        })''')
        assert state['muted'] and state['autoplay'] and state['loop']
        assert state['playsInline'] and not state['error'] and not errors
        browser_version = browser.version
        await browser.close()
    names = ['demo.mp4', 'demo.gif', 'demo-poster.png']
    receipt = {
        'browser_version': browser_version,
        'autoplay_policy_overridden': False,
        'scope': 'Local docs/demo.html in headless Chromium/Chrome; GitHub README motion remains viewer-controlled',
        'page_errors': errors, 'video_state': state, 'gif': gif_info,
        'video': {'codec': stream['codec_name'], 'pixel_format': stream['pix_fmt'],
                  'width': stream['width'], 'height': stream['height'],
                  'duration_seconds': float(probe['format']['duration'])},
        'artifact_sha256': {name: hashlib.sha256((assets/name).read_bytes()).hexdigest()
                            for name in names},
    }
    (assets / 'demo-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    asyncio.run(verify(parser.parse_args().project))
