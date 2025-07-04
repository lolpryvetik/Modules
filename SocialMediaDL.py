# ©️ SocialMediaDL - Social Media Downloader, LoLpryvet, 2025
# 🌐 https://github.com/lolpryvetik/Modules/SocialMediaDL
# Licensed under GNU AGPL v3.0
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# meta developer: @LoLpryvet

import aiohttp
import asyncio
import re
import os
import json
import warnings
import functools
import logging
import tempfile
import shutil
from io import BytesIO

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from typing import Union, Optional, List, Dict, Any
from .. import loader, utils

try:
    from PIL import Image, ImageFilter
    import subprocess
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False

__version__ = (3, 0, 0)

@dataclass
class TTData:
    dir_name: str
    media: Union[str, List[str]]
    type: str


@dataclass
class PinData:
    id: str
    url: str
    title: str
    description: str
    media_type: str  
    media_urls: List[str]
    board_name: Optional[str] = None
    user_name: Optional[str] = None
    created_at: Optional[str] = None


class TikTokAPI:
    def __init__(self, host: Optional[str] = None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) "
            "Version/4.0.4 Mobile/7B334b Safari/531.21.10"
        }
        self.host = host or "https://www.tikwm.com/"
        self.session = aiohttp.ClientSession()

        self.data_endpoint = "api"
        self.search_videos_keyword_endpoint = "api/feed/search"
        self.search_videos_hashtag_endpoint = "api/challenge/search"

        self.link = None
        self.result = None
        self.progress_message = None

        self.logger = logging.getLogger("SocialMediaDL-TikTok")
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[SocialMediaDL-TikTok:%(funcName)s]: %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _warn(reason: str = "This function is NOT used but may be useful"):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                warnings.warn(
                    f"Warning! Deprecated: {func.__name__}\nReason: {reason}",
                    category=DeprecationWarning,
                    stacklevel=2,
                )
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def set_progress_message(self, message):
        
        self.progress_message = message

    async def _update_progress(self, text: str):
        
        if self.progress_message:
            try:
                await utils.answer(self.progress_message, text)
            except:
                pass

    async def close_session(self):
        await self.session.close()

    async def _ensure_data(self, link: str):
        try:
            if self.result is None or self.link != link:
                self.link = link
                self.result = await self.fetch(link)
                self.logger.info("Successfully ensured data from the link")
        except Exception as e:
            self.logger.error(f"Error occurred when trying to get data from tikwm: {e}")
            raise

    async def __getimages(self, download_dir: Optional[str] = None):
        download_dir = download_dir or self.result["id"]
        os.makedirs(download_dir, exist_ok=True)
        
        total_images = len(self.result["images"])
        downloaded = 0
        
        for i, url in enumerate(self.result["images"]):
            progress = int((i / total_images) * 100)
            progress_bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
            await self._update_progress(
                f"<emoji document_id=5434105584834067115>📥</emoji><b> Загрузка изображений... {progress}%</b>\n"
                f"<code>[{progress_bar}]</code>\n"
                f"<blockquote>Изображение {i + 1} из {total_images}</blockquote>"
            )
            
            await self._download_file(url, os.path.join(download_dir, f"image_{i + 1}.jpg"))
            downloaded += 1

        await self._update_progress(
            f"<emoji document_id=5434105584834067115>✅</emoji><b> Все изображения загружены!</b>\n"
            f"<code>[██████████]</code>\n"
            f"<blockquote>Загружено: {downloaded} из {total_images}</blockquote>"
        )
        
        self.logger.info(f"Images - Downloaded and saved photos to {download_dir}")

        return TTData(
            dir_name=download_dir,
            media=[
                os.path.join(download_dir, f"image_{i + 1}.jpg")
                for i in range(len(self.result["images"]))
            ],
            type="images",
        )

    async def __getvideo(self, video_filename: Optional[str] = None, hd: bool = False):
        video_url = self.result["hdplay"] if hd else self.result["play"]
        video_filename = video_filename or f"{self.result['id']}.mp4"

        async with self.session.get(video_url) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            last_percent = 0

            with open(video_filename, "wb") as file:
                async for chunk in response.content.iter_chunked(8192):
                    file.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        if percent >= last_percent + 10 and percent != 0:
                            last_percent = percent
                            progress_bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
                            await self._update_progress(
                                f"<emoji document_id=5434105584834067115>📥</emoji><b> Загрузка видео... {percent}%</b>\n"
                                f"<code>[{progress_bar}]</code>\n"
                                f"<blockquote>{downloaded // 1024 // 1024} MB из {total_size // 1024 // 1024} MB</blockquote>"
                            )

        await self._update_progress(
            f"<emoji document_id=5434105584834067115>✅</emoji><b> Видео загружено!</b>\n"
            f"<code>[██████████]</code>\n"
            f"<blockquote>Размер файла: {os.path.getsize(video_filename) // 1024 // 1024} MB</blockquote>"
        )
        
        self.logger.info(f"Video - Downloaded and saved video as {video_filename}")

        return TTData(
            dir_name=os.path.dirname(video_filename), media=video_filename, type="video"
        )

    async def _makerequest(self, endpoint: str, params: dict) -> dict:
        async with self.session.get(
            urljoin(self.host, endpoint), params=params, headers=self.headers
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("data", {})

    @staticmethod
    def get_url(text: str) -> Optional[str]:
        urls = re.findall(r"http[s]?://[^\s]+", text)
        return urls[0] if urls else None

    async def convert_share_urls(self, url: str) -> Optional[str]:
        url = self.get_url(url)
        if "@" in url and "tiktok.com" in url:
            return url
            
        if any(domain in url for domain in ["vt.tiktok.com", "vm.tiktok.com"]):
            try:
                async with self.session.get(
                    url, headers=self.headers, allow_redirects=True
                ) as response:
                    final_url = str(response.url)
                    if "tiktok.com" in final_url:
                        return final_url.split("?")[0]
            except Exception as e:
                self.logger.error(f"Error resolving share URL: {e}")
                
        return url

    @_warn()
    async def get_tiktok_video_id(self, original_url: str) -> Optional[str]:
        original_url = await self.convert_share_urls(original_url)
        matches = re.findall(r"/video|v|photo/(\d+)", original_url)
        return matches[0] if matches else None

    async def fetch(self, link: str) -> dict:
        url = await self.convert_share_urls(link)
        params = {"url": url, "hd": 1}
        return await self._makerequest(self.data_endpoint, params=params)

    async def _download_file(self, url: str, path: str):
        async with self.session.get(url) as response:
            response.raise_for_status()
            with open(path, "wb") as file:
                while chunk := await response.content.read(1024):
                    file.write(chunk)

    async def download_sound(
        self,
        link: Union[str],
        audio_filename: Optional[str] = None,
        audio_ext: Optional[str] = ".mp3",
    ):
        await self._ensure_data(link)

        if not audio_filename:
            audio_filename = f"{self.result['music_info']['title']}{audio_ext}"
        else:
            audio_filename += audio_ext

        async with self.session.get(self.result["music_info"]["play"]) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            last_percent = 0

            with open(audio_filename, "wb") as file:
                async for chunk in response.content.iter_chunked(8192):
                    file.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        if percent >= last_percent + 20 and percent != 0:
                            last_percent = percent
                            progress_bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
                            await self._update_progress(
                                f"<emoji document_id=5434105584834067115>📥</emoji><b> Загрузка аудио... {percent}%</b>\n"
                                f"<code>[{progress_bar}]</code>\n"
                                f"<blockquote>{downloaded // 1024} KB из {total_size // 1024} KB</blockquote>"
                            )

        await self._update_progress(
            f"<emoji document_id=5434105584834067115>✅</emoji><b> Аудио загружено!</b>\n"
            f"<code>[██████████]</code>\n"
            f"<blockquote>Размер файла: {os.path.getsize(audio_filename) // 1024} KB</blockquote>"
        )
        
        self.logger.info(f"Sound - Downloaded and saved sound as {audio_filename}")
        return audio_filename

    async def download(
        self, link: Union[str], video_filename: Optional[str] = None, hd: bool = True
    ) -> TTData:
        await self._ensure_data(link)
        if "images" in self.result:
            self.logger.info("Starting to download images")
            return await self.__getimages(video_filename)
        elif "hdplay" in self.result or "play" in self.result:
            self.logger.info("Starting to download video.")
            return await self.__getvideo(video_filename, hd)
        else:
            self.logger.error("No downloadable content found in the provided link.")
            raise Exception("No downloadable content found in the provided link.")

    async def download_photos_with_sound(self, link: Union[str]) -> str:
        await self._ensure_data(link)
        
        if "images" not in self.result:
            raise Exception("This TikTok post doesn't contain photos")
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            total_images = len(self.result["images"])
            image_paths = []
            
            for i, url in enumerate(self.result["images"]):
                progress = int((i / total_images) * 50)
                progress_bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
                await self._update_progress(
                    f"<emoji document_id=5434105584834067115>📥</emoji><b> Загрузка изображений... {progress}%</b>\n"
                    f"<code>[{progress_bar}]</code>\n"
                    f"<blockquote>Изображение {i + 1} из {total_images}</blockquote>"
                )
                
                image_path = os.path.join(temp_dir, f"image_{i}.jpg")
                await self._download_file(url, image_path)
                image_paths.append(image_path)
            
            await self._update_progress(
                f"<emoji document_id=5434105584834067115>📥</emoji><b> Загрузка аудио... 75%</b>\n"
                f"<code>[███████░░░]</code>\n"
                f"<blockquote>Загружается звуковая дорожка...</blockquote>"
            )
            
            sound_path = os.path.join(temp_dir, "sound.mp3")
            await self._download_file(self.result["music_info"]["play"], sound_path)
            
            await self._update_progress(
                f"<emoji document_id=5434105584834067115>🎬</emoji><b> Создание видео... 90%</b>\n"
                f"<code>[█████████░]</code>\n"
                f"<blockquote>Объединяем изображения и звук...</blockquote>"
            )
            
            output_video = os.path.join(temp_dir, f"{self.result['id']}_with_sound.mp4")
            await self._create_slideshow_video(image_paths, sound_path, output_video)
            
            await self._update_progress(
                f"<emoji document_id=5434105584834067115>✅</emoji><b> Видео создано!</b>\n"
                f"<code>[██████████]</code>\n"
                f"<blockquote>Готово к отправке!</blockquote>"
            )
            
            self.logger.info(f"Photo+Sound Video - Created video: {output_video}")
            return output_video
            
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise e

    async def _create_slideshow_video(self, image_paths: List[str], sound_path: str, output_path: str):
        if not FFMPEG_AVAILABLE:
            raise Exception("FFmpeg is required for creating videos. Please install ffmpeg.")
        
        probe_cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', sound_path
        ]
        
        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            audio_duration = float(result.stdout.strip())
        except:
            audio_duration = 15.0
        
        num_images = len(image_paths)
        duration_per_image = audio_duration / num_images
        
        target_width = 1080
        target_height = 1920
        
        max_area = 0
        for img_path in image_paths:
            try:
                with Image.open(img_path) as img:
                    area = img.width * img.height
                    if area > max_area:
                        max_area = area
                        aspect_ratio = img.width / img.height
                        if aspect_ratio > 1:
                            target_width = 1920
                            target_height = int(1920 / aspect_ratio)
                        else:
                            target_height = 1920
                            target_width = int(1920 * aspect_ratio)
            except Exception:
                continue
        
        target_width = target_width + (target_width % 2)
        target_height = target_height + (target_height % 2)
        
        processed_images = []
        
        for i, img_path in enumerate(image_paths):
            processed_path = os.path.join(os.path.dirname(img_path), f"uniform_{i}.jpg")
            
            try:
                with Image.open(img_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    img_resized = img.copy()
                    
                    scale_w = target_width / img.width
                    scale_h = target_height / img.height
                    scale = min(scale_w, scale_h)
                    
                    new_width = int(img.width * scale)
                    new_height = int(img.height * scale)
                    
                    img_resized = img_resized.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    canvas = Image.new('RGB', (target_width, target_height), (0, 0, 0))
                    paste_x = (target_width - new_width) // 2
                    paste_y = (target_height - new_height) // 2
                    canvas.paste(img_resized, (paste_x, paste_y))
                    
                    canvas.save(processed_path, 'JPEG', quality=95)
                    processed_images.append(processed_path)
                    
            except Exception as e:
                self.logger.error(f"Error processing image {img_path}: {e}")
                fallback_path = os.path.join(os.path.dirname(img_path), f"fallback_{i}.jpg")
                black_img = Image.new('RGB', (target_width, target_height), (0, 0, 0))
                black_img.save(fallback_path, 'JPEG', quality=95)
                processed_images.append(fallback_path)
        
        if len(processed_images) == 1:
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', processed_images[0],
                '-i', sound_path,
                '-c:v', 'libx264', '-r', '60', '-t', str(audio_duration),
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-shortest',
                '-preset', 'fast', '-crf', '18',
                output_path
            ]
        else:
            input_args = []
            filter_parts = []
            
            for img_path in processed_images:
                input_args.extend(['-loop', '1', '-t', str(duration_per_image), '-i', img_path])
            
            input_args.extend(['-i', sound_path])
            
            fade_duration = min(0.5, duration_per_image / 2)
            
            if len(processed_images) > 1:
                current_stream = "[0:v]"
                
                for i in range(1, len(processed_images)):
                    if i == 1:
                        filter_parts.append(f"{current_stream}[{i}:v]xfade=transition=fade:duration={fade_duration}:offset={duration_per_image-fade_duration}[v{i}]")
                        current_stream = f"[v{i}]"
                    else:
                        offset_time = (i * duration_per_image) - fade_duration
                        filter_parts.append(f"{current_stream}[{i}:v]xfade=transition=fade:duration={fade_duration}:offset={offset_time}[v{i}]")
                        current_stream = f"[v{i}]"
                
                filter_complex = ";".join(filter_parts)
            else:
                filter_complex = "[0:v]null[v1]"
                current_stream = "[v1]"
            
            ffmpeg_cmd = [
                'ffmpeg', '-y'
            ] + input_args + [
                '-filter_complex', filter_complex,
                '-map', current_stream, '-map', f'{len(processed_images)}:a',
                '-c:v', 'libx264', '-r', '60', '-c:a', 'aac',
                '-pix_fmt', 'yuv420p', '-shortest',
                '-preset', 'fast', '-crf', '18',
                output_path
            ]
        
        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=True)
            self.logger.info("Successfully created slideshow video with FFmpeg")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg error: {e.stderr}")
            raise Exception(f"Failed to create video: {e.stderr}")


class PinterestAPI:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers=self.headers
        )
        
        self.progress_message = None
        
        self.logger = logging.getLogger("SocialMediaDL-Pinterest")
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[SocialMediaDL-Pinterest:%(funcName)s]: %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def set_progress_message(self, message):
        self.progress_message = message

    async def _update_progress(self, text: str):
        if self.progress_message:
            try:
                await utils.answer(self.progress_message, text)
            except:
                pass

    async def close_session(self):
        await self.session.close()

    def _extract_pin_id(self, url: str) -> Optional[str]:
        patterns = [
            r'pinterest\.com/pin/(\d+)',
            r'pinterest\.com.*?/pin/(\d+)',
            r'/pin/(\d+)',
            r'pin\.it/([a-zA-Z0-9]+)',
            r'pinterest\.com.*?pin.*?(\d{10,})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                pin_id = match.group(1)
                self.logger.info(f"Extracted pin ID: {pin_id} from URL: {url}")
                return pin_id
        
        self.logger.warning(f"Could not extract pin ID from URL: {url}")
        return None

    def _is_pinterest_url(self, url: str) -> bool:
        return any(domain in url.lower() for domain in [
            'pinterest.com', 'pin.it', 'pinterest.co.uk', 'pinterest.ca',
            'pinterest.fr', 'pinterest.de', 'pinterest.es', 'pinterest.it'
        ])

    async def _resolve_short_url(self, url: str) -> str:
        if 'pin.it' in url:
            try:
                await self._update_progress(
                    "<emoji document_id=5434105584834067115>🔄</emoji><b> Разрешение короткой ссылки...</b>"
                )
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
                
                try:
                    async with self.session.get(url, headers=headers, allow_redirects=False) as response:
                        if response.status in [301, 302, 303, 307, 308]:
                            location = response.headers.get('Location')
                            if location and 'pinterest.com' in location:
                                self.logger.info(f"Resolved {url} to {location}")
                                return location
                except Exception as e:
                    self.logger.warning(f"Redirect method failed: {e}")
                
                try:
                    async with self.session.get(url, headers=headers, allow_redirects=True) as response:
                        final_url = str(response.url)
                        if 'pinterest.com' in final_url and final_url != url:
                            self.logger.info(f"Resolved {url} to {final_url}")
                            return final_url.split('?')[0]
                except Exception as e:
                    self.logger.warning(f"Full redirect method failed: {e}")
                
                pin_id = self._extract_pin_id(url)
                if pin_id and pin_id != 'unknown':
                    manual_url = f"https://www.pinterest.com/pin/{pin_id}/"
                    self.logger.info(f"Created manual URL: {manual_url}")
                    return manual_url
                
            except Exception as e:
                self.logger.error(f"Error resolving short URL {url}: {e}")
                
        return url

    async def _download_file(self, url: str, path: str, file_index: int = 0, total_files: int = 1) -> bool:
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                headers = self.headers.copy()
                headers.update({
                    'Referer': 'https://www.pinterest.com/',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                })
                
                async with self.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        total_size = int(response.headers.get('content-length', 0))
                        
                        if not any(media_type in content_type.lower() for media_type in ['image', 'video', 'octet-stream']):
                            self.logger.warning(f"Unexpected content type for {url}: {content_type}")
                        
                        downloaded = 0
                        last_percent = 0
                        
                        with open(path, 'wb') as file:
                            async for chunk in response.content.iter_chunked(8192):
                                file.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    percent = int((downloaded / total_size) * 100)
                                    if percent >= last_percent + 20 and percent != 0:
                                        last_percent = percent
                                        progress_bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
                                        await self._update_progress(
                                            f"<emoji document_id=5434105584834067115>📥</emoji><b> Загрузка файла {file_index + 1} из {total_files}... {percent}%</b>\n"
                                            f"<code>[{progress_bar}]</code>\n"
                                            f"<blockquote>{downloaded // 1024} KB из {total_size // 1024} KB</blockquote>"
                                        )
                        
                        if os.path.exists(path) and os.path.getsize(path) > 0:
                            self.logger.info(f"Successfully downloaded {url} to {path}")
                            return True
                        else:
                            self.logger.error(f"Downloaded file is empty: {path}")
                            return False
                    else:
                        self.logger.error(f"Failed to download {url}: HTTP {response.status}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        return False
                        
            except Exception as e:
                self.logger.error(f"Error downloading {url} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return False
        
        return False

    async def _extract_pin_data_from_page(self, url: str) -> Optional[PinData]:
        try:
            await self._update_progress(
                "<emoji document_id=5434105584834067115>🔍</emoji><b> Извлечение данных пина...</b>"
            )
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    self.logger.error(f"Failed to fetch Pinterest page: HTTP {response.status}")
                    return None
                
                html = await response.text()
                
                pin_data = await self._extract_from_script_tags(html, url)
                if pin_data:
                    return pin_data
                
                pin_data = self._extract_from_meta_tags(html, url)
                if pin_data:
                    return pin_data
                
                pin_data = self._extract_from_html_elements(html, url)
                if pin_data:
                    return pin_data
                
                return None
                
        except Exception as e:
            self.logger.error(f"Error extracting pin data from {url}: {e}")
            return None

    async def _extract_from_script_tags(self, html: str, url: str) -> Optional[PinData]:
        try:
            json_patterns = [
                r'<script[^>]*id="__PWS_INITIAL_PROPS__"[^>]*>([^<]+)</script>',
                r'<script[^>]*id="initial-state"[^>]*>([^<]+)</script>',
                r'<script[^>]*>window\.__PWS_INITIAL_PROPS__\s*=\s*({.+?});</script>',
                r'<script[^>]*>window\.__PWS_DATA__\s*=\s*({.+?});</script>',
                r'<script[^>]*type="application/ld\+json"[^>]*>([^<]+)</script>',
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    try:
                        json_str = match.strip()
                        if json_str.startswith('window.'):
                            continue
                            
                        data = json.loads(json_str)
                        pin_data = self._parse_pin_data(data, url)
                        if pin_data:
                            return pin_data
                    except (json.JSONDecodeError, Exception):
                        continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting from script tags: {e}")
            return None

    def _parse_pin_data(self, data: Dict[str, Any], url: str) -> Optional[PinData]:
        try:
            pin_info = None
            
            if 'props' in data and 'initialReduxState' in data['props']:
                redux_state = data['props']['initialReduxState']
                
                if 'pins' in redux_state:
                    pins = redux_state['pins']
                    if pins:
                        pin_info = next(iter(pins.values()))
                
                if not pin_info and 'resources' in redux_state:
                    resources = redux_state['resources']
                    if 'PinResource' in resources:
                        pin_resources = resources['PinResource']
                        if pin_resources:
                            pin_info = next(iter(pin_resources.values()))
            
            elif 'pin' in data:
                pin_info = data['pin']
            
            elif 'data' in data:
                pin_info = data['data']
                if isinstance(pin_info, list) and pin_info:
                    pin_info = pin_info[0]
            
            elif 'resource_response' in data:
                resource = data['resource_response']
                if 'data' in resource:
                    pin_info = resource['data']
            
            elif '@type' in data and data['@type'] == 'ImageObject':
                return self._parse_jsonld_data(data, url)
            
            if not pin_info:
                return None
            
            media_urls = []
            media_type = 'image'
            
            video_url = self._extract_video_url(pin_info)
            if video_url:
                media_urls.append(video_url)
                media_type = 'video'
            
            if not media_urls:
                image_urls = self._extract_image_urls(pin_info)
                media_urls.extend(image_urls)
            
            if not media_urls:
                return None
            
            pin_id = (
                self._extract_pin_id(url) or 
                pin_info.get('id') or 
                pin_info.get('pin_id') or 
                'unknown'
            )
            
            title = pin_info.get('title', '') or pin_info.get('rich_summary', {}).get('display_name', '')
            description = pin_info.get('description', '') or pin_info.get('rich_summary', {}).get('display_description', '')
            
            user_name = None
            board_name = None
            
            if 'pinner' in pin_info:
                pinner = pin_info['pinner']
                if isinstance(pinner, dict):
                    user_name = pinner.get('username') or pinner.get('full_name')
            
            if 'board' in pin_info:
                board = pin_info['board']
                if isinstance(board, dict):
                    board_name = board.get('name')
            
            return PinData(
                id=str(pin_id),
                url=url,
                title=title,
                description=description,
                media_type=media_type,
                media_urls=media_urls,
                board_name=board_name,
                user_name=user_name,
                created_at=pin_info.get('created_at')
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing pin data: {e}")
            return None

    def _extract_video_url(self, pin_info: Dict[str, Any]) -> Optional[str]:
        try:
            if 'videos' in pin_info and pin_info['videos']:
                video_list = pin_info['videos'].get('video_list', {})
                if video_list:
                    for quality in ['V_HLSV4', 'V_720P', 'V_EXP7', 'V_EXP6', 'V_EXP5', 'V_EXP4']:
                        if quality in video_list:
                            video_data = video_list[quality]
                            if isinstance(video_data, dict) and 'url' in video_data:
                                return video_data['url']
            
            video_keys = ['video_url', 'video_source', 'video_large_url', 'video_medium_url']
            for key in video_keys:
                if key in pin_info and pin_info[key]:
                    return pin_info[key]
            
            if 'rich_metadata' in pin_info:
                rich_data = pin_info['rich_metadata']
                if isinstance(rich_data, dict):
                    for key in ['video_url', 'source_url']:
                        if key in rich_data and rich_data[key]:
                            return rich_data[key]
            
            return None
            
        except Exception:
            return None

    def _extract_image_urls(self, pin_info: Dict[str, Any]) -> List[str]:
        try:
            urls = []
            
            if 'images' in pin_info and pin_info['images']:
                images = pin_info['images']
                
                size_priority = ['orig', '736x', '564x', '474x', '236x', 'original']
                
                for size in size_priority:
                    if size in images:
                        image_data = images[size]
                        if isinstance(image_data, dict) and 'url' in image_data:
                            urls.append(image_data['url'])
                        elif isinstance(image_data, str):
                            urls.append(image_data)
                
                if not urls:
                    for size, image_data in images.items():
                        if isinstance(image_data, dict) and 'url' in image_data:
                            urls.append(image_data['url'])
                        elif isinstance(image_data, str):
                            urls.append(image_data)
            
            image_keys = [
                'image_large_url', 'image_medium_url', 'image_url', 
                'image_medium_sized_url', 'image_large_sized_url'
            ]
            
            for key in image_keys:
                if key in pin_info and pin_info[key]:
                    urls.append(pin_info[key])
            
            if 'rich_metadata' in pin_info:
                rich_data = pin_info['rich_metadata']
                if isinstance(rich_data, dict):
                    for key in ['image_url', 'source_url']:
                        if key in rich_data and rich_data[key]:
                            urls.append(rich_data[key])
            
            unique_urls = []
            for url in urls:
                if url and url not in unique_urls and ('pinimg.com' in url or 'pinterest' in url):
                    unique_urls.append(url)
            
            return unique_urls
            
        except Exception:
            return []

    def _parse_jsonld_data(self, data: Dict[str, Any], url: str) -> Optional[PinData]:
        try:
            media_urls = []
            media_type = 'image'
            
            if 'contentUrl' in data:
                media_urls.append(data['contentUrl'])
            elif 'url' in data:
                media_urls.append(data['url'])
            
            if not media_urls:
                return None
            
            pin_id = self._extract_pin_id(url) or 'unknown'
            
            return PinData(
                id=str(pin_id),
                url=url,
                title=data.get('name', ''),
                description=data.get('description', ''),
                media_type=media_type,
                media_urls=media_urls
            )
            
        except Exception:
            return None

    def _extract_from_meta_tags(self, html: str, url: str) -> Optional[PinData]:
        try:
            meta_patterns = {
                'title': [
                    r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"',
                    r'<meta[^>]*name="twitter:title"[^>]*content="([^"]*)"',
                    r'<title[^>]*>([^<]*)</title>',
                ],
                'description': [
                    r'<meta[^>]*property="og:description"[^>]*content="([^"]*)"',
                    r'<meta[^>]*name="twitter:description"[^>]*content="([^"]*)"',
                    r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
                ],
                'image': [
                    r'<meta[^>]*property="og:image"[^>]*content="([^"]*)"',
                    r'<meta[^>]*name="twitter:image"[^>]*content="([^"]*)"',
                    r'<meta[^>]*property="og:image:secure_url"[^>]*content="([^"]*)"',
                    r'<link[^>]*rel="image_src"[^>]*href="([^"]*)"',
                ],
                'video': [
                    r'<meta[^>]*property="og:video"[^>]*content="([^"]*)"',
                    r'<meta[^>]*property="og:video:secure_url"[^>]*content="([^"]*)"',
                    r'<meta[^>]*name="twitter:player"[^>]*content="([^"]*)"',
                ],
            }
            
            meta_data = {}
            for key, patterns in meta_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        meta_data[key] = match.group(1)
                        break
            
            if not meta_data.get('image'):
                img_patterns = [
                    r'<img[^>]*src="([^"]*pinimg\.com[^"]*originals[^"]*)"',
                    r'<img[^>]*src="([^"]*pinimg\.com[^"]*736x[^"]*)"',
                    r'<img[^>]*src="([^"]*pinimg\.com[^"]*564x[^"]*)"',
                ]
                
                for pattern in img_patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        meta_data['image'] = match.group(1)
                        break
            
            if not meta_data.get('video'):
                video_patterns = [
                    r'"video_url":"([^"]*)"',
                    r'"url":"([^"]*\.mp4[^"]*)"',
                    r'src="([^"]*\.mp4[^"]*)"',
                ]
                
                for pattern in video_patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        meta_data['video'] = match.group(1)
                        break
            
            if not meta_data.get('image') and not meta_data.get('video'):
                return None
            
            media_urls = []
            media_type = 'image'
            
            if meta_data.get('video'):
                media_urls.append(meta_data['video'])
                media_type = 'video'
            
            if meta_data.get('image'):
                media_urls.append(meta_data['image'])
            
            if not media_urls:
                return None
            
            pin_id = self._extract_pin_id(url) or 'unknown'
            
            return PinData(
                id=str(pin_id),
                url=url,
                title=meta_data.get('title', '').replace(' | Pinterest', ''),
                description=meta_data.get('description', ''),
                media_type=media_type,
                media_urls=media_urls
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting from meta tags: {e}")
            return None

    def _extract_from_html_elements(self, html: str, url: str) -> Optional[PinData]:
        try:
            media_urls = []
            
            img_patterns = [
                r'<img[^>]*src="([^"]*pinimg\.com[^"]*)"[^>]*>',
                r'<img[^>]*data-src="([^"]*pinimg\.com[^"]*)"[^>]*>',
                r'<img[^>]*srcset="([^"]*pinimg\.com[^"]*)"[^>]*>',
            ]
            
            for pattern in img_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    urls = re.findall(r'(https://[^\s,]+)', match)
                    for img_url in urls:
                        if 'pinimg.com' in img_url and img_url not in media_urls:
                            if any(size in img_url for size in ['originals', '736x', '564x']):
                                media_urls.insert(0, img_url)
                            else:
                                media_urls.append(img_url)
            
            video_patterns = [
                r'<video[^>]*src="([^"]*)"[^>]*>',
                r'<source[^>]*src="([^"]*)"[^>]*>',
                r'"video_url":"([^"]*)"',
                r'"url":"([^"]*\.mp4[^"]*)"',
            ]
            
            for pattern in video_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    if match not in media_urls:
                        media_urls.insert(0, match)
            
            if not media_urls:
                return None
            
            unique_urls = []
            for url_item in media_urls:
                if url_item not in unique_urls:
                    unique_urls.append(url_item)
            
            pin_id = self._extract_pin_id(url) or 'unknown'
            
            media_type = 'video' if any('.mp4' in u or 'video' in u for u in unique_urls) else 'image'
            
            return PinData(
                id=str(pin_id),
                url=url,
                title='Pinterest Pin',
                description='',
                media_type=media_type,
                media_urls=unique_urls[:5]
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting from HTML elements: {e}")
            return None

    async def get_pin_data(self, url: str) -> Optional[PinData]:
        if not self._is_pinterest_url(url):
            return None
        
        full_url = await self._resolve_short_url(url)
        
        return await self._extract_pin_data_from_page(full_url)

    async def download_pin(self, url: str, download_dir: Optional[str] = None) -> Optional[List[str]]:
        pin_data = await self.get_pin_data(url)
        if not pin_data:
            return None
        
        if not download_dir:
            download_dir = tempfile.mkdtemp()
        
        os.makedirs(download_dir, exist_ok=True)
        
        downloaded_files = []
        
        await self._update_progress(
            f"<emoji document_id=5434105584834067115>📥</emoji><b> Начинаем загрузку {len(pin_data.media_urls)} файлов...</b>"
        )
        
        for i, media_url in enumerate(pin_data.media_urls):
            if not media_url or not media_url.startswith('http'):
                continue
                
            parsed_url = urlparse(media_url)
            path_parts = parsed_url.path.split('.')
            extension = path_parts[-1] if len(path_parts) > 1 else 'jpg'
            
            extension = re.sub(r'[^a-zA-Z0-9]', '', extension)
            if not extension:
                extension = 'mp4' if pin_data.media_type == 'video' else 'jpg'
            
            filename = f"pinterest_{pin_data.id}_{i+1}.{extension}"
            filepath = os.path.join(download_dir, filename)
            
            if await self._download_file(media_url, filepath, i, len(pin_data.media_urls)):
                downloaded_files.append(filepath)
                self.logger.info(f"Downloaded: {filename}")
            else:
                self.logger.error(f"Failed to download: {media_url}")
        
        if downloaded_files:
            await self._update_progress(
                f"<emoji document_id=5434105584834067115>✅</emoji><b> Загрузка завершена! {len(downloaded_files)} файлов готово.</b>"
            )
        
        return downloaded_files if downloaded_files else None


@loader.tds
class SocialMediaDL(loader.Module):
    """Social Media Downloader - Download from TikTok, Pinterest, Instagram"""
    
    strings = {
        "name": "SocialMediaDL",
        "downloading": "<emoji document_id=5434105584834067115>🤑</emoji><b> Загрузка...</b>",
        "creating_video": "<emoji document_id=5434105584834067115>🎬</emoji><b> Создание видео из фото и звука…</b>",
        "success": "<b>✅ Успешно загружено!</b>",
        "error": "<b>❌ Произошла ошибка при загрузке:</b>\n<code>{}</code>",
        "no_reply": "<b>❌ Ответьте на сообщение со ссылкой или укажите ссылку в аргументах.</b>",
        "no_link": "<b>❌ Ссылка не найдена в сообщении.</b>",
        "no_media": "<b>❌ Медиа не найдено.</b>",
        "no_photos": "<b>❌ Этот пост не содержит фотографий.</b>",
        "ffmpeg_missing": "<b>❌ Для создания видео требуется FFmpeg. Установите ffmpeg и PIL (Pillow).</b>",
        "instagram_processing": "<emoji document_id='6318766236746384900'>🕔</emoji> <b>Обработка Instagram...</b>",
        "instagram_success": "<b>✅ Instagram контент успешно загружен</b> <emoji document_id='6320882302708614449'>🚀</emoji>",
        "pin_info": "<b>📌 Информация о пине:</b>\n<b>🏷️ Заголовок:</b> {title}\n<b>📝 Описание:</b> {description}\n<b>👤 Пользователь:</b> {user}\n<b>📋 Доска:</b> {board}",
        "trying_methods": "<b>🔄 Пробуем различные методы извлечения...</b>",
        "debug_info": "<b>🔍 Отладочная информация:</b>\n<b>Исходная ссылка:</b> <code>{original_url}</code>\n<b>Разрешенная ссылка:</b> <code>{resolved_url}</code>\n<b>ID пина:</b> <code>{pin_id}</code>",
    }

    strings_ru = {
        "downloading": "<emoji document_id=5434105584834067115>🤑</emoji><b> Загрузка...</b>",
        "creating_video": "<emoji document_id=5434105584834067115>🎬</emoji><b> Создание видео из фото и звука…</b>",
        "success": "<b>✅ Успешно загружено!</b>",
        "error": "<b>❌ Произошла ошибка при загрузке:</b>\n<code>{}</code>",
        "no_reply": "<b>❌ Ответьте на сообщение со ссылкой или укажите ссылку в аргументах.</b>",
        "no_link": "<b>❌ Ссылка не найдена в сообщении.</b>",
        "no_media": "<b>❌ Медиа не найдено.</b>",
        "no_photos": "<b>❌ Этот пост не содержит фотографий.</b>",
        "ffmpeg_missing": "<b>❌ Для создания видео требуется FFmpeg. Установите ffmpeg и PIL (Pillow).</b>",
        "instagram_processing": "<emoji document_id='6318766236746384900'>🕔</emoji> <b>Обработка Instagram...</b>",
        "instagram_success": "<b>✅ Instagram контент успешно загружен</b> <emoji document_id='6320882302708614449'>🚀</emoji>",
        "pin_info": "<b>📌 Информация о пине:</b>\n<b>🏷️ Заголовок:</b> {title}\n<b>📝 Описание:</b> {description}\n<b>👤 Пользователь:</b> {user}\n<b>📋 Доска:</b> {board}",
        "trying_methods": "<b>🔄 Пробуем различные методы извлечения...</b>",
        "debug_info": "<b>🔍 Отладочная информация:</b>\n<b>Исходная ссылка:</b> <code>{original_url}</code>\n<b>Разрешенная ссылка:</b> <code>{resolved_url}</code>\n<b>ID пина:</b> <code>{pin_id}</code>",
    }

    def __init__(self):
        super().__init__()
        self.tiktok_api = TikTokAPI()
        self.pinterest_api = PinterestAPI()
        self.instagram_chat = "@SaveAsBot"
        
        self.logger = logging.getLogger("SocialMediaDL-Module")
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[SocialMediaDL-Module:%(funcName)s]: %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    async def on_unload(self):
        
        await self.tiktok_api.close_session()
        await self.pinterest_api.close_session()

    def _extract_url(self, text: str) -> tuple[Optional[str], str]:
        
        if not text:
            return None, "unknown"
        
        import html
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', '', text)
        
        
        tiktok_patterns = [
            r'https?://(?:www\.)?tiktok\.com/[@\w\d._-]+/video/\d+',
            r'https?://vm\.tiktok\.com/[\w\d]+',
            r'https?://vt\.tiktok\.com/[\w\d]+',
            r'https?://(?:www\.)?tiktok\.com/@[\w\d._-]+/video/\d+',
            r'https?://(?:m\.)?tiktok\.com/v/\d+',
        ]
        
        for pattern in tiktok_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0), "tiktok"
        
        
        pinterest_patterns = [
            r'https?://pin\.it/[a-zA-Z0-9]+',
            r'https?://(?:www\.)?pinterest\.com/pin/\d+',
            r'https?://(?:www\.)?pinterest\.co\.uk/pin/\d+',
            r'https?://(?:www\.)?pinterest\.ca/pin/\d+',
            r'https?://(?:www\.)?pinterest\.fr/pin/\d+',
            r'https?://(?:www\.)?pinterest\.de/pin/\d+',
            r'https?://(?:www\.)?pinterest\.es/pin/\d+',
            r'https?://(?:www\.)?pinterest\.it/pin/\d+',
            r'pin\.it/[a-zA-Z0-9]+',
            r'pinterest\.com/pin/\d+',
        ]
        
        for pattern in pinterest_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = match.group(0)
                if not url.startswith('http'):
                    url = 'https://' + url
                url = re.sub(r'[^\w\d\-/.:]', '', url.split()[0])
                return url, "pinterest"
        
       
        instagram_patterns = [
            r'https?://(?:www\.)?instagram\.com/(?:p|tv|reel)/[\w\-]+',
            r'https?://(?:www\.)?instagram\.com/stories/[\w\d._-]+/\d+',
            r'https?://instagr\.am/p/[\w\-]+',
        ]
        
        for pattern in instagram_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0), "instagram"
        
        return None, "unknown"

    async def _get_url_from_message(self, message) -> tuple[Optional[str], str]:
       
        args = utils.get_args(message)
        url = None
        platform = "unknown"
        
        if args:
            url, platform = self._extract_url(" ".join(args))
        
        if not url and message.is_reply:
            reply = await message.get_reply_message()
            if reply:
                if reply.text:
                    url, platform = self._extract_url(reply.text)
                if not url and hasattr(reply, 'caption') and reply.caption:
                    url, platform = self._extract_url(reply.caption)
        
        return url, platform

    @loader.command(
        ru_doc="Скачать видео или фото с TikTok (ответьте на сообщение со ссылкой или укажите ссылку)",
        en_doc="Download videos or photos from TikTok (reply to message with link or provide link)",
    )
    async def tt(self, message):
        """Download videos or photos from TikTok"""
        url, platform = await self._get_url_from_message(message)
        
        if not url or platform != "tiktok":
            await utils.answer(message, self.strings("no_reply"))
            return

        loading_msg = await utils.answer(message, self.strings("downloading"))
        self.tiktok_api.set_progress_message(loading_msg)
        files_to_cleanup = []

        try:
            download_result = await self.tiktok_api.download(url)

            if download_result.type == "video":
                files_to_cleanup.append(download_result.media)
                await message.client.send_file(
                    message.to_id,
                    download_result.media
                )
                await loading_msg.delete()
            elif download_result.type == "images":
                if isinstance(download_result.media, list):
                    files_to_cleanup.extend(download_result.media)
                else:
                    files_to_cleanup.append(download_result.media)
                
                await message.client.send_file(
                    message.to_id,
                    download_result.media
                )
                await loading_msg.delete()

        except Exception as e:
            await utils.answer(loading_msg, self.strings("error").format(e))
        finally:
            if 'download_result' in locals():
                for file_path in files_to_cleanup:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        self.logger.error(f"Error cleaning up file {file_path}: {e}")
                
                if files_to_cleanup and hasattr(download_result, 'dir_name') and download_result.dir_name:
                    try:
                        if os.path.exists(download_result.dir_name) and not os.listdir(download_result.dir_name):
                            os.rmdir(download_result.dir_name)
                    except Exception as e:
                        self.logger.error(f"Error cleaning up directory {download_result.dir_name}: {e}")

    @loader.command(
        ru_doc="Скачать звук с TikTok (ответьте на сообщение со ссылкой или укажите ссылку)",
        en_doc="Download sound from TikTok (reply to message with link or provide link)",
    )
    async def ttsound(self, message):
       
        url, platform = await self._get_url_from_message(message)
        
        if not url or platform != "tiktok":
            await utils.answer(message, self.strings("no_reply"))
            return

        loading_msg = await utils.answer(message, self.strings("downloading"))
        self.tiktok_api.set_progress_message(loading_msg)
        sound_file_path = None

        try:
            sound_file_path = await self.tiktok_api.download_sound(url)
            await message.client.send_file(
                message.to_id, sound_file_path
            )
            await loading_msg.delete()
        except Exception as e:
            await utils.answer(
                loading_msg,
                f"{self.strings('error').format(e)}\n Убедитесь, что ссылка ведет именно на видео или фото с нужным звуком, прямая ссылка на звук не сработает!",
            )
        finally:
            if sound_file_path and os.path.exists(sound_file_path):
                try:
                    os.remove(sound_file_path)
                    self.logger.info(f"Cleaned up sound file: {sound_file_path}")
                except Exception as e:
                    self.logger.error(f"Error cleaning up sound file {sound_file_path}: {e}")

    @loader.command(
        ru_doc="Скачать фото с TikTok и создать видео со звуком (ответьте на сообщение со ссылкой или укажите ссылку)",
        en_doc="Download TikTok photos and create video with sound (reply to message with link or provide link)",
    )
    async def ftt(self, message):
        """Download TikTok photos and create video with sound"""
        if not FFMPEG_AVAILABLE:
            await utils.answer(message, self.strings("ffmpeg_missing"))
            return
            
        url, platform = await self._get_url_from_message(message)
        
        if not url or platform != "tiktok":
            await utils.answer(message, self.strings("no_reply"))
            return

        loading_msg = await utils.answer(message, self.strings("downloading"))
        self.tiktok_api.set_progress_message(loading_msg)
        temp_video_path = None

        try:
            temp_video_path = await self.tiktok_api.download_photos_with_sound(url)
            
            await message.client.send_file(
                message.to_id,
                temp_video_path
            )
            await loading_msg.delete()

        except Exception as e:
            if "doesn't contain photos" in str(e):
                await utils.answer(loading_msg, self.strings("no_photos"))
            else:
                await utils.answer(loading_msg, self.strings("error").format(e))
        finally:
            if temp_video_path and os.path.exists(temp_video_path):
                temp_dir = os.path.dirname(temp_video_path)
                shutil.rmtree(temp_dir, ignore_errors=True)

    # Pinterest Commands
    @loader.command(
        ru_doc="Загрузить медиа из Pinterest (ответьте на сообщение со ссылкой или укажите ссылку)",
        en_doc="Download media from Pinterest (reply to message with link or provide link)",
    )
    async def pin(self, message):
        """Download media from Pinterest"""
        url, platform = await self._get_url_from_message(message)
        
        if not url or platform != "pinterest":
            await utils.answer(message, self.strings("no_reply"))
            return

        loading_msg = await utils.answer(message, self.strings("downloading"))
        self.pinterest_api.set_progress_message(loading_msg)

        downloaded_files = []
        temp_dir = None

        try:
            temp_dir = tempfile.mkdtemp()
            
            downloaded_files = await self.pinterest_api.download_pin(url, temp_dir)
            
            if not downloaded_files:
                await utils.answer(loading_msg, self.strings("trying_methods"))
                
            
            if not downloaded_files:
                resolved_url = await self.pinterest_api._resolve_short_url(url)
                pin_id = self.pinterest_api._extract_pin_id(url)
                
                debug_text = self.strings("debug_info").format(
                    original_url=url,
                    resolved_url=resolved_url,
                    pin_id=pin_id or "Not found"
                )
                
                await utils.answer(loading_msg, f"{self.strings('no_media')}\n\n{debug_text}")
                return
            
            for file_path in downloaded_files:
                try:
                    await message.client.send_file(
                        message.to_id,
                        file_path
                    )
                except Exception as e:
                    self.logger.error(f"Error sending file {file_path}: {e}")
            
            await loading_msg.delete()

        except Exception as e:
            self.logger.error(f"Error in pin command: {e}")
            await utils.answer(loading_msg, self.strings("error").format(str(e)))
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    @loader.command(
        ru_doc="Получить информацию о пине Pinterest (ответьте на сообщение со ссылкой или укажите ссылку)",
        en_doc="Get Pinterest pin information (reply to message with link or provide link)",
    )
    async def pininfo(self, message):
        """Get Pinterest pin information"""
        url, platform = await self._get_url_from_message(message)
        
        if not url or platform != "pinterest":
            await utils.answer(message, self.strings("no_reply"))
            return

        loading_msg = await utils.answer(message, self.strings("downloading"))
        self.pinterest_api.set_progress_message(loading_msg)

        try:
            pin_data = await self.pinterest_api.get_pin_data(url)
            
            if not pin_data:
                await utils.answer(loading_msg, self.strings("no_media"))
                return
            
            info_text = self.strings("pin_info").format(
                title=pin_data.title[:100] + "..." if len(pin_data.title) > 100 else pin_data.title,
                description=pin_data.description[:200] + "..." if len(pin_data.description) > 200 else pin_data.description,
                user=pin_data.user_name or "Unknown",
                board=pin_data.board_name or "Unknown"
            )
            
            info_text += f"\n<b>🎬 Media Type:</b> {pin_data.media_type.title()}"
            info_text += f"\n<b>📊 Media Count:</b> {len(pin_data.media_urls)}"
            info_text += f"\n<b>🆔 Pin ID:</b> <code>{pin_data.id}</code>"
            
            await utils.answer(loading_msg, info_text)

        except Exception as e:
            await utils.answer(loading_msg, self.strings("error").format(str(e)))

    @loader.command(
        ru_doc="Быстрая загрузка из Pinterest (оригинальный способ через внешний сервис)",
        en_doc="Quick Pinterest download (original method via external service)",
    )
    async def pinterest(self, message):
        """Quick Pinterest download via external service"""
        url, platform = await self._get_url_from_message(message)
        
        if not url or platform != "pinterest":
            await utils.answer(message, self.strings("no_reply"))
            return
        
        if 'pin.it' in url:
            download_link = f"https://pinterestdownloader.com?share_url={url}"
            await utils.answer(
                message, 
                f'<emoji document_id=5319172556345851345>✨</emoji> <b><u>Pin ready to download!</u></b>\n\n'
                f'<emoji document_id=5316719099227684154>🌕</emoji> <b>Link for download:</b> '
                f'<i><a href="{download_link}">just tap here</a></i>'
            )
        else:
            await utils.answer(
                message, 
                f"<emoji document_id=5319088379281815108>🤷‍♀️</emoji> '{url}' <b>doesn't contain</b> 'pin.it' \n\n"
                f"<b>Try using the .pin command for direct download</b>"
            )

    
    @loader.group_member
    @loader.command(
        ru_doc="Скачать видео/фото из Instagram (укажите ссылку)",
        en_doc="Download video/photo from Instagram (provide link)",
    )
    async def insta(self, message):
        """Download video/reels/photo from Instagram"""
        url, platform = await self._get_url_from_message(message)
        
        if not url or platform != "instagram":
            await utils.answer(message, self.strings("no_reply"))
            return
        
        loading_msg = await utils.answer(message, self.strings("instagram_processing"))
        
        try:
            async with self._client.conversation(self.instagram_chat) as conv:
                msgs = []
                msgs += [await conv.send_message("/start")]
                msgs += [await conv.get_response()]
                msgs += [await conv.send_message(url)]
                m = await conv.get_response()

            await self._client.send_file(
                message.peer_id,
                m.media,
                reply_to=message.reply_to_msg_id,
            )

            for msg in msgs + [m]:
                await msg.delete()

            if message.out:
                await message.delete()

            await self.client.delete_dialog(self.instagram_chat)
            
            if loading_msg:
                await loading_msg.delete()

        except Exception as e:
            await utils.answer(loading_msg, self.strings("error").format(str(e)))

    
    @loader.command(
        ru_doc="Универсальная загрузка с TikTok, Pinterest, Instagram (автоопределение платформы)",
        en_doc="Universal download from TikTok, Pinterest, Instagram (auto-detect platform)",
    )
    async def dl(self, message):
        """Universal download from social media platforms"""
        url, platform = await self._get_url_from_message(message)
        
        if not url or platform == "unknown":
            await utils.answer(message, self.strings("no_reply"))
            return
        
        
        if platform == "tiktok":
            await self.tt(message)
        elif platform == "pinterest":
            await self.pin(message)
        elif platform == "instagram":
            await self.insta(message)
        else:
            await utils.answer(message, self.strings("no_link"))

    @loader.command(
        ru_doc="Показать информацию о поддерживаемых платформах",
        en_doc="Show information about supported platforms",
    )
    async def dlinfo(self, message):
        """Show supported platforms and commands"""
        info_text = """
<b>🌐 SocialMediaDL - Unified Social Media Downloader</b>

<b>📱 Поддерживаемые платформы:</b>
• <b>TikTok</b> - видео, фото, звук
• <b>Pinterest</b> - изображения, видео
• <b>Instagram</b> - видео, фото, reels

<b>🔧 Команды:</b>

<b>TikTok:</b>
• <code>.tt</code> - скачать видео/фото
• <code>.ttsound</code> - скачать звук
• <code>.ftt</code> - создать видео из фото со звуком

<b>Pinterest:</b>
• <code>.pin</code> - скачать медиа
• <code>.pininfo</code> - информация о пине
• <code>.pinterest</code> - быстрая загрузка

<b>Instagram:</b>
• <code>.insta</code> - скачать видео/фото

<b>Универсальные:</b>
• <code>.dl</code> - автоопределение платформы
• <code>.dlinfo</code> - эта справка

<b>💡 Использование:</b>
Просто ответьте на сообщение со ссылкой или укажите ссылку в команде.
        """
        await utils.answer(message, info_text)