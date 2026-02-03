import os
import requests
import sys
import re
from urllib.parse import urlparse, unquote, urljoin
from bs4 import BeautifulSoup
import time

def get_filename_from_cd(cd):
    """Get filename from content-disposition"""
    if not cd:
        return None
    fname = re.findall('filename=(.+)', cd)
    if len(fname) == 0:
        return None
    return fname[0].strip('"').strip("'")

def clean_filename(filename):
    """Sanitize filename"""
    return re.sub(r'[\\/*?:":<>|]', "", filename)

def is_audio_url(url):
    """Check if URL looks like an audio file"""
    exts = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma']
    return any(url.lower().endswith(e) for e in exts)

def find_audio_on_page(html_content, base_url):
    """Deep search for audio links in HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    candidates = []

    # 1. <audio> tags
    for audio in soup.find_all('audio'):
        if audio.get('src'):
            candidates.append(audio.get('src'))
        for source in audio.find_all('source'):
            if source.get('src'):
                candidates.append(source.get('src'))

    # 2. <a> tags with audio extensions
    for a in soup.find_all('a', href=True):
        if is_audio_url(a['href']):
            candidates.append(a['href'])
            
    # 3. <source> tags generic
    for source in soup.find_all('source', src=True):
        if is_audio_url(source['src']):
            candidates.append(source['src'])
    
    # 4. Meta tags (Open Graph / Twitter)
    for meta in soup.find_all('meta'):
        if meta.get('property') in ['og:audio', 'og:audio:url', 'og:audio:secure_url'] or \
           meta.get('name') in ['twitter:player:stream', 'twitter:audio:partner']:
            if meta.get('content'):
                candidates.append(meta.get('content'))

    # 5. Regex search in scripts/json (simple)
    # Look for http...mp3 inside strings
    # This catches links inside JSON or JS variables
    text_matches = re.findall(r'https?://[^\s"\\]+\.mp3', html_content)
    candidates.extend(text_matches)

    # Resolve relative URLs
    resolved = []
    for c in candidates:
        if not c: continue
        full_url = urljoin(base_url, c)
        resolved.append(full_url)
    
    # Return unique, prioritized list (mp3 first)
    unique = []
    seen = set()
    for r in resolved:
        if r not in seen:
            seen.add(r)
            unique.append(r)
            
    # Sort to prefer mp3
    unique.sort(key=lambda x: 0 if x.lower().endswith('.mp3') else 1)
    
    return unique

def get_wayback_url(url):
    """Try to find the latest snapshot from Wayback Machine"""
    print(f"Checking Wayback Machine for: {url}")
    api_url = f"http://archive.org/wayback/available?url={url}"
    try:
        r = requests.get(api_url, timeout=10)
        data = r.json()
        if data.get('archived_snapshots') and data['archived_snapshots'].get('closest'):
            return data['archived_snapshots']['closest']['url']
    except Exception as e:
        print(f"Wayback check failed: {e}")
    return None

def download_file(url, output_dir, referer=None):
    """Download a direct file"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        if referer:
            headers['Referer'] = referer

        print(f"Attempting download: {url}")
        r = requests.get(url, headers=headers, stream=True, timeout=15)
        
        # Check if we got a file or a page
        content_type = r.headers.get('content-type', '').lower()
        if 'text/html' in content_type and not is_audio_url(url):
            # It's a page, return the content so we can parse it
            return False, r.text, r.url

        r.raise_for_status()

        # Filename guessing
        filename = get_filename_from_cd(r.headers.get('content-disposition'))
        if not filename:
            path = urlparse(r.url).path
            filename = unquote(os.path.basename(path))
        
        if not filename or '.' not in filename:
            # Try to guess from content-type
            ext = '.mp3'
            if 'wav' in content_type: ext = '.wav'
            elif 'ogg' in content_type: ext = '.ogg'
            filename = f"downloaded_audio{ext}"
        
        filename = clean_filename(filename)
        output_path = os.path.join(output_dir, filename)

        # Handle duplicates
        counter = 1
        base, ext = os.path.splitext(output_path)
        while os.path.exists(output_path):
            output_path = f"{base}_{counter}{ext}"
            counter += 1

        print(f"Saving to: {output_path}")
        total_size = int(r.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"Progress: {percent:.1f}%", end='\r')
        
        print(f"\nSuccess! File saved.")
        return True, output_path, None

    except Exception as e:
        print(f"Download failed: {e}")
        return False, None, None

def process_url(url, output_dir="downloads", try_wayback=True):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. Try direct download
    success, result_content, final_url = download_file(url, output_dir)
    if success:
        return result_content # Return path

    # 2. If it was HTML, search for links
    html_content = result_content # in this case, result_content is html text
    if html_content:
        print("URL is a webpage. Scanning for audio...")
        audio_links = find_audio_on_page(html_content, final_url)
        
        if audio_links:
            print(f"Found {len(audio_links)} candidate audio link(s).")
            for link in audio_links:
                print(f"Trying candidate: {link}")
                s, path, _ = download_file(link, output_dir, referer=final_url)
                if s:
                    return path
        else:
            print("No audio links found in page content.")

    # 3. Wayback Machine Fallback
    if try_wayback:
        print("\n--- Trying Wayback Machine Auto-Fix ---")
        wb_url = get_wayback_url(url)
        if wb_url:
            print(f"Found archived version: {wb_url}")
            return process_url(wb_url, output_dir, try_wayback=False)
        else:
            print("No archived version found.")
            
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mp3_downloader.py <URL>")
    else:
        target_url = sys.argv[1]
        process_url(target_url)
