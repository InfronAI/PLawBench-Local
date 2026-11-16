"""Record real browser interactions with a completed report, then make MP4/GIF.

Requires: pip install playwright; python -m playwright install chromium ffmpeg
Or use the installed Google Chrome browser (detected automatically).
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


async def record(report, destination):
    from playwright.async_api import async_playwright
    errors = []
    interactions = []
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='plawbench-video-') as temp:
        async with async_playwright() as p:
            options = {'headless': True, 'timeout': 45000}
            chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
            if not Path(p.chromium.executable_path).exists() and chrome.exists():
                options['executable_path'] = str(chrome)
            browser = await p.chromium.launch(**options)
            context = await browser.new_context(viewport={'width':1280,'height':900},
                                                device_scale_factor=1,
                                                record_video_dir=temp,
                                                record_video_size={'width':1280,'height':900})
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto(report.resolve().as_uri())
            await page.wait_for_selector('#list button')
            coverage = await page.evaluate('DATA.summary.coverage')
            quality_summary = await page.locator('#quality').inner_text()
            assert 'generated' in quality_summary
            await page.screenshot(path=str(destination/'demo-poster.png'))
            await page.wait_for_timeout(2200)
            await page.locator('.explorer').scroll_into_view_if_needed()
            await page.wait_for_timeout(1200)
            for task, tab in [('case_analysis','response'),('case_analysis','grade'),
                              ('consultation','question'),('consultation','response'),
                              ('consultation','rubric'),('plaintiff','response'),('defendant','grade')]:
                await page.select_option('#task', task)
                await page.click(f'[data-tab="{tab}"]')
                await page.wait_for_timeout(2400)
                interactions.append({'task':task,'tab':tab,'title':await page.locator('#detailsTitle').inner_text()})
                assert task in await page.locator('#detailsTitle').inner_text()
                assert await page.locator('#content').inner_text()
            await page.fill('#search','not-a-real-id')
            assert await page.locator('#count').inner_text() == '0 records'
            await page.click('[data-tab="grade"]')
            assert await page.locator('#content').inner_text() == 'No matching records'
            await page.fill('#search','')
            await page.select_option('#task','all')
            await page.evaluate('window.scrollTo({top:0,behavior:"smooth"})')
            await page.wait_for_timeout(1800)
            video = page.video
            await context.close()
            source = await video.path()
            await browser.close()
        if errors:
            raise RuntimeError(f'Browser errors: {errors}')
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',source,'-an','-c:v','libx264',
                        '-preset','medium','-crf','24','-pix_fmt','yuv420p','-movflags','+faststart',
                        str(destination/'demo.mp4')],check=True)
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(destination/'demo.mp4'),
                        '-filter_complex','fps=6,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer',
                        '-loop','0',str(destination/'demo.gif')],check=True)
    receipt = {'report':str(report),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),
               'browser':'Chromium/Chrome via Playwright','page_errors':errors,
               'coverage':coverage,'quality_summary':quality_summary,'empty_filter_guard_checked':True,
               'interactions':interactions,'source':'Actual rendered report; no synthetic model output',
               'artifacts':['demo.mp4','demo.gif','demo-poster.png'],
               'artifact_sha256':{name:hashlib.sha256((destination/name).read_bytes()).hexdigest()
                                  for name in ['demo.mp4','demo.gif','demo-poster.png']}}
    (destination/'demo-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('docs/assets'))
    args=parser.parse_args()
    asyncio.run(record(args.report,args.output))
