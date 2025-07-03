# ©️ LoLpryvet, 2025
# 🌐 https://https://github.com/lolpryvetik/Modules/TTDL.py
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
import warnings
import functools
import logging
import tempfile
import shutil
from io import BytesIO

from dataclasses import dataclass
from urllib.parse import urljoin
from typing import Union, Optional, List
from tqdm import tqdm
from .. import loader, utils

try:
    from PIL import Image, ImageFilter
    import subprocess
    FFMPEG_AVAILABLE = True
except ImportError:
    FFMPEG_AVAILABLE = False


@dataclass
class data:
    dir_name: str
    media: Union[str, List[str]]
    type: str


class TikTok:
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

        self.logger = logging.getLogger("damirtag-TikTok")
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[damirtag-TikTok:%(funcName)s]: %(levelname)s - %(message)s"
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
        tasks = [
            self._download_file(url, os.path.join(download_dir, f"image_{i + 1}.jpg"))
            for i, url in enumerate(self.result["images"])
        ]
        await asyncio.gather(*tasks)
        self.logger.info(f"Images - Downloaded and saved photos to {download_dir}")

        return data(
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
            with open(video_filename, "wb") as file:
                with tqdm(
                    total=total_size, unit="B", unit_scale=True, desc=video_filename
                ) as pbar:
                    async for chunk in response.content.iter_any():
                        file.write(chunk)
                        pbar.update(len(chunk))

        self.logger.info(f"Video - Downloaded and saved video as {video_filename}")

        return data(
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

        await self._download_file(self.result["music_info"]["play"], audio_filename)
        self.logger.info(f"Sound - Downloaded and saved sound as {audio_filename}")
        return audio_filename

    async def download(
        self, link: Union[str], video_filename: Optional[str] = None, hd: bool = True
    ) -> data:
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
            image_paths = []
            for i, url in enumerate(self.result["images"]):
                image_path = os.path.join(temp_dir, f"image_{i}.jpg")
                await self._download_file(url, image_path)
                image_paths.append(image_path)
            
            sound_path = os.path.join(temp_dir, "sound.mp3")
            await self._download_file(self.result["music_info"]["play"], sound_path)
            
            output_video = os.path.join(temp_dir, f"{self.result['id']}_with_sound.mp4")
            await self._create_slideshow_video(image_paths, sound_path, output_video)
            
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

    def _get_video_link(self, unique_id: str, aweme_id: str) -> str:
        return f"https://www.tiktok.com/@{unique_id}/video/{aweme_id}"

    def _get_uploader_link(self, unique_id: str) -> str:
        return f"https://www.tiktok.com/@{unique_id}"


@loader.tds
class TTDL(loader.Module):
    strings = {
        "name": "TTDL",
        "downloading": "<b>Downloading…</b>",
        "creating_video": "<b>Creating video from photos and sound…</b>",
        "success_photo": "<b>The photo(s) has/have been successfully downloaded!</b>",
        "success_video": "<b>The video has been successfully downloaded!</b>",
        "success_sound": "<b>The sound has been successfully downloaded!</b>",
        "success_photo_video": "<b>Photo slideshow with sound has been created!</b>",
        "error": "Error occurred while downloading.\n{}",
        "no_reply": "Reply to a message with TikTok link or provide a link as argument.",
        "no_tiktok_link": "No TikTok link found in the message.",
        "no_photos": "This TikTok post doesn't contain photos.",
        "ffmpeg_missing": "FFmpeg is required for .ftt command. Please install ffmpeg and PIL (Pillow).",
    }

    strings_ru = {
        "downloading": "<b>Загружаем…</b>",
        "creating_video": "<b>Создаём видео из фото и звука…</b>",
        "success_photo": "<b>Фотография(-и) была(-и) успешно загружены!</b>",
        "success_video": "<b>Видео было успешно загружено!</b>",
        "success_sound": "<b>Звук был успешно загружен!</b>",
        "success_photo_video": "<b>Слайдшоу из фото со звуком создано!</b>",
        "error": "Во время загрузки произошла ошибка.\n{}",
        "no_reply": "Ответьте на сообщение со ссылкой на TikTok или укажите ссылку в аргументах.",
        "no_tiktok_link": "Ссылка на TikTok не найдена в сообщении.",
        "no_photos": "Этот TikTok пост не содержит фотографий.",
        "ffmpeg_missing": "Для команды .ftt требуется FFmpeg. Установите ffmpeg и PIL (Pillow).",
    }

    def _extract_tiktok_url(self, text: str) -> Optional[str]:
        if not text:
            return None
        
        patterns = [
            r'https?://(?:www\.)?tiktok\.com/[@\w\d._-]+/video/\d+',
            r'https?://vm\.tiktok\.com/[\w\d]+',
            r'https?://vt\.tiktok\.com/[\w\d]+',
            r'https?://(?:www\.)?tiktok\.com/@[\w\d._-]+/video/\d+',
            r'https?://(?:m\.)?tiktok\.com/v/\d+',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return None

    @loader.command(
        ru_doc="Скачать звук с TikTok (ответьте на сообщение со ссылкой или укажите ссылку)",
        en_doc="Download sound from TikTok (reply to message with link or provide link)",
    )
    async def ttsound(self, message):
        args = utils.get_args(message)
        url = None
        
        if args:
            url = self._extract_tiktok_url(" ".join(args))
        
        if not url and message.is_reply:
            reply = await message.get_reply_message()
            if reply and reply.text:
                url = self._extract_tiktok_url(reply.text)
        
        if not url:
            await utils.answer(message, self.strings("no_reply"))
            return
        
        if not any(domain in url.lower() for domain in ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com']):
            await utils.answer(message, self.strings("no_tiktok_link"))
            return

        await utils.answer(message, self.strings("downloading"))

        tiktok_downloader = TikTok()
        sound_file_path = None

        try:
            sound_file_path = await tiktok_downloader.download_sound(url)
            await message.client.send_file(
                message.to_id, sound_file_path
            )
            await message.delete()
        except Exception as e:
            await utils.answer(
                message,
                f"{self.strings('error').format(e)}\n Убедитесь, что ссылка ведет именно на видео или фото с нужным звуком, прямая ссылка на звук не сработает!",
            )
        finally:
            if sound_file_path and os.path.exists(sound_file_path):
                try:
                    os.remove(sound_file_path)
                    self.logger.info(f"Cleaned up sound file: {sound_file_path}")
                except Exception as e:
                    self.logger.error(f"Error cleaning up sound file {sound_file_path}: {e}")
            
            await tiktok_downloader.close_session()

    @loader.command(
        ru_doc="Скачать фото с TikTok и создать видео со звуком (ответьте на сообщение со ссылкой или укажите ссылку)",
        en_doc="Download TikTok photos and create video with sound (reply to message with link or provide link)",
    )
    async def ftt(self, message):
        if not FFMPEG_AVAILABLE:
            await utils.answer(message, self.strings("ffmpeg_missing"))
            return
            
        args = utils.get_args(message)
        url = None
        
        if args:
            url = self._extract_tiktok_url(" ".join(args))
        
        if not url and message.is_reply:
            reply = await message.get_reply_message()
            if reply and reply.text:
                url = self._extract_tiktok_url(reply.text)
        
        if not url:
            await utils.answer(message, self.strings("no_reply"))
            return
        
        if not any(domain in url.lower() for domain in ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com']):
            await utils.answer(message, self.strings("no_tiktok_link"))
            return

        await utils.answer(message, self.strings("downloading"))

        tiktok_downloader = TikTok()
        temp_video_path = None

        try:
            await utils.answer(message, self.strings("creating_video"))
            temp_video_path = await tiktok_downloader.download_photos_with_sound(url)
            
            await message.client.send_file(
                message.to_id,
                temp_video_path
            )
            await message.delete()

        except Exception as e:
            if "doesn't contain photos" in str(e):
                await utils.answer(message, self.strings("no_photos"))
            else:
                await utils.answer(message, self.strings("error").format(e))
        finally:
            if temp_video_path and os.path.exists(temp_video_path):
                temp_dir = os.path.dirname(temp_video_path)
                shutil.rmtree(temp_dir, ignore_errors=True)
            await tiktok_downloader.close_session()

    @loader.command(
        ru_doc="Скачать видео или фото с TikTok (ответьте на сообщение со ссылкой или укажите ссылку)",
        en_doc="Download videos or photos from TikTok (reply to message with link or provide link)",
    )
    async def tt(self, message):
        args = utils.get_args(message)
        url = None
        
        if args:
            url = self._extract_tiktok_url(" ".join(args))
        
        if not url and message.is_reply:
            reply = await message.get_reply_message()
            if reply and reply.text:
                url = self._extract_tiktok_url(reply.text)
        
        if not url:
            await utils.answer(message, self.strings("no_reply"))
            return
        
        if not any(domain in url.lower() for domain in ['tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com']):
            await utils.answer(message, self.strings("no_tiktok_link"))
            return

        await utils.answer(message, self.strings("downloading"))

        tiktok_downloader = TikTok()
        files_to_cleanup = []

        try:
            download_result = await tiktok_downloader.download(url)

            if download_result.type == "video":
                files_to_cleanup.append(download_result.media)
                await message.client.send_file(
                    message.to_id,
                    download_result.media
                )
                await message.delete()
            elif download_result.type == "images":
                if isinstance(download_result.media, list):
                    files_to_cleanup.extend(download_result.media)
                else:
                    files_to_cleanup.append(download_result.media)
                
                await message.client.send_file(
                    message.to_id,
                    download_result.media
                )
                await message.delete()

        except Exception as e:
            await utils.answer(message, self.strings("error").format(e))
        finally:
            for file_path in files_to_cleanup:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        self.logger.info(f"Cleaned up file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error cleaning up file {file_path}: {e}")
            
            if files_to_cleanup and download_result.dir_name:
                try:
                    if os.path.exists(download_result.dir_name) and not os.listdir(download_result.dir_name):
                        os.rmdir(download_result.dir_name)
                        self.logger.info(f"Cleaned up directory: {download_result.dir_name}")
                except Exception as e:
                    self.logger.error(f"Error cleaning up directory {download_result.dir_name}: {e}")
            
            await tiktok_downloader.close_session()