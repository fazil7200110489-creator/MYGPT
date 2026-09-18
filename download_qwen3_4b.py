"""Fast Multi-threaded Resumable Downloader for Qwen3-4B-Q4_K_M.gguf
Downloads directly from official Hugging Face repository Qwen/Qwen3-4B-GGUF with 16 parallel workers.
"""

import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor

URL = "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf"
OUTPUT_PATH = r"d:\MYGPT\models\local_llm\Qwen3-4B-Q4_K_M.gguf"
TEMP_DIR = r"d:\MYGPT\models\local_llm\temp_parts"
NUM_THREADS = 16


def download_part(url, start_byte, end_byte, part_file):
    expected_size = end_byte - start_byte + 1
    current_size = os.path.getsize(part_file) if os.path.exists(part_file) else 0

    if current_size >= expected_size:
        return True

    actual_start = start_byte + current_size
    headers = {"Range": f"bytes={actual_start}-{end_byte}"}

    for attempt in range(8):
        try:
            r = requests.get(url, headers=headers, stream=True, timeout=25)
            if r.status_code in [200, 206]:
                mode = "ab" if current_size > 0 else "wb"
                with open(part_file, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 512):
                        if chunk:
                            f.write(chunk)
                if os.path.getsize(part_file) >= expected_size:
                    return True
        except Exception as e:
            time.sleep(1.5)
            current_size = os.path.getsize(part_file) if os.path.exists(part_file) else 0
            actual_start = start_byte + current_size
            headers = {"Range": f"bytes={actual_start}-{end_byte}"}
    return os.path.getsize(part_file) >= expected_size


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    print(f"Connecting to official Hugging Face URL: {URL}")
    head_resp = requests.head(URL, allow_redirects=True, timeout=15)
    total_size = int(head_resp.headers.get("Content-Length", 0))

    if total_size == 0:
        print("Failed to determine file size.")
        return False

    print(f"Total Model File Size: {total_size:,} bytes ({total_size / (1024**3):.2f} GB)")

    part_size = total_size // NUM_THREADS
    futures = []
    part_files = []

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        for i in range(NUM_THREADS):
            start = i * part_size
            end = total_size - 1 if i == NUM_THREADS - 1 else (start + part_size - 1)
            part_file = os.path.join(TEMP_DIR, f"part_{i}.bin")
            part_files.append(part_file)
            futures.append(executor.submit(download_part, URL, start, end, part_file))

        print(f"Dispatched {NUM_THREADS} download workers. Monitoring progress...")
        last_downloaded = 0
        while not all(f.done() for f in futures):
            downloaded = sum(os.path.getsize(p) for p in part_files if os.path.exists(p))
            pct = (downloaded / total_size) * 100
            elapsed = time.time() - t0
            speed_mb = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            print(f"Progress: {downloaded:,} / {total_size:,} bytes ({pct:.1f}%) @ {speed_mb:.2f} MB/s", flush=True)
            time.sleep(4)

    for f in futures:
        if not f.result():
            print("Download failed for one or more parts.")
            return False

    print("All 16 parts downloaded. Merging into final GGUF file...")
    with open(OUTPUT_PATH, "wb") as outfile:
        for p in part_files:
            with open(p, "rb") as infile:
                while True:
                    buf = infile.read(1024 * 1024 * 8)
                    if not buf:
                        break
                    outfile.write(buf)
            os.remove(p)

    try:
        os.rmdir(TEMP_DIR)
    except Exception:
        pass

    final_size = os.path.getsize(OUTPUT_PATH)
    total_time = time.time() - t0
    avg_speed = (final_size / (1024 * 1024)) / total_time if total_time > 0 else 0

    print("=" * 60)
    print(f"SUCCESS: Genuine Qwen3-4B-Q4_K_M.gguf downloaded successfully!")
    print(f"Final Path:  {OUTPUT_PATH}")
    print(f"Final Size:  {final_size:,} bytes ({final_size / (1024**3):.2f} GB)")
    print(f"Total Time:  {total_time:.1f} s ({avg_speed:.2f} MB/s)")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
