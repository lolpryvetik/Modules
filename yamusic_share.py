# ©️ LoLpryvet, 2025
# 🌐 https://github.com/lolpryvetik/Modules/blob/main/yamusic_share.py
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

# Name: YaMusicShare
# Description: Поделиться текущим треком как в Яндекс.Музыке (дополнение к YaMusic)
# meta developer: @LoLpryvet
# requires: aiohttp pillow yandex-music requests

import asyncio
import logging
import tempfile
import aiohttp
import os
import re
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageStat
import colorsys
import yandex_music
import requests

from telethon import types

from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class YaMusicShare(loader.Module):
    """Поделиться текущим треком как в Яндекс.Музыке (дополнение к YaMusic)"""

    strings = {
        "name": "YaMusicShare",
        "no_yamusic_module": "<emoji document_id=5854929766146118183>❌</emoji> <b>Модуль YaMusic не найден!</b>\n\n<i>Установи модуль YaMusic и авторизуйся через него с токеном Яндекс.Музыки</i>",
        "no_auth_token": "<emoji document_id=5854929766146118183>❌</emoji> <b>Не авторизован в Яндекс.Музыке!</b>\n\n<i>Укажи токен в конфиге модуля YaMusic</i>",
        "no_song_playing": "<emoji document_id=5854929766146118183>❌</emoji> <b>Сейчас ничего не играет.</b>",
        "track_loading": "<emoji document_id=5334768819548200731>💻</emoji> <b>Создаю карточку...</b>",
        "auth_error": "<emoji document_id=5854929766146118183>❌</emoji> <b>Ошибка авторизации:</b> <code>{}</code>",
        "unexpected_error": "<emoji document_id=5854929766146118183>❌</emoji> <b>Произошла ошибка:</b> <code>{}</code>",
    }

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

    def _get_yamusic_module(self):
        """Получает модуль YaMusic если он установлен"""
        try:
            for module in self.allmodules.modules:
                if hasattr(module, 'strings') and module.strings.get('name') == 'YaMusic':
                    return module
            return None
        except Exception as e:
            logger.error(f"Error getting YaMusic module: {e}")
            return None

    def _get_yamusic_token(self):
        """Получает токен авторизации из модуля YaMusic"""
        yamusic_module = self._get_yamusic_module()
        if not yamusic_module:
            return None
        
        try:
            return yamusic_module.config.get('token')
        except Exception as e:
            logger.error(f"Error getting token from YaMusic: {e}")
            return None

    async def _get_lyrics_from_yamusic(self, client, track_id):
        """Получает текст песни через Яндекс.Музыку API"""
        try:
            lyrics = client.tracks_lyrics(track_id)
            if lyrics and lyrics.download_url:
                lyrics_text = requests.get(lyrics.download_url).text
                
                lines = [line.strip() for line in lyrics_text.split('\n') if line.strip()]
                return lines[:3] if lines else None
            return None
        except Exception as e:
            logger.debug(f"No lyrics found for track {track_id}: {e}")
            return None

    def _get_dominant_color(self, image):
        """Получает доминирующий цвет изображения"""
        small_image = image.resize((50, 50))
        stat = ImageStat.Stat(small_image)
        r, g, b = stat.mean
        return int(r), int(g), int(b)

    def _create_gradient_background(self, width, height, base_color):
        """Создает градиентный фон на основе базового цвета"""
        r, g, b = base_color
        
        
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        v = max(0.1, v * 0.3)  
        s = min(1.0, s * 1.2)
        dark_r, dark_g, dark_b = colorsys.hsv_to_rgb(h, s, v)
        dark_r, dark_g, dark_b = int(dark_r * 255), int(dark_g * 255), int(dark_b * 255)
        
        
        img = Image.new('RGB', (width, height))
        
        
        for y in range(height):
            
            factor = 1 - (y / height) * 0.8  
            
            final_r = int(r * factor + dark_r * (1 - factor))
            final_g = int(g * factor + dark_g * (1 - factor))
            final_b = int(b * factor + dark_b * (1 - factor))
            
            
            final_r = max(0, min(255, final_r))
            final_g = max(0, min(255, final_g))
            final_b = max(0, min(255, final_b))
            
            for x in range(width):
                img.putpixel((x, y), (final_r, final_g, final_b))
        
        return img

    def _get_optimal_font_size(self, text, max_width, max_height, font_path, initial_size=28):
        """Находит оптимальный размер шрифта для помещения текста в заданные границы"""
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='ignore')
        
        font_size = initial_size
        min_size = 12
        
        while font_size >= min_size:
            try:
                if font_path:
                    try:
                        font = ImageFont.truetype(font_path, font_size)
                    except:
                        font = ImageFont.load_default()
                else:
                    font = ImageFont.load_default()
                
                temp_img = Image.new('RGB', (1, 1))
                temp_draw = ImageDraw.Draw(temp_img, "RGBA")
                
                try:
                    bbox = temp_draw.textbbox((0, 0), str(text), font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    if text_width <= max_width and text_height <= max_height:
                        return font
                except:
                    pass
                
                font_size -= 1
            except:
                font_size -= 1
        
        return ImageFont.load_default()

    def _wrap_text(self, text, max_width, font, draw):
        """Переносит текст на новые строки если он не помещается"""
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='ignore')
        
        text = str(text)
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font)
                test_width = bbox[2] - bbox[0]
                
                if test_width <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        truncated = word[:15] + "..." if len(word) > 15 else word
                        lines.append(truncated)
            except:
                current_line.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else [text[:20] + "..." if len(text) > 20 else text]

    async def _create_yamusic_share_card(self, track_info, lyrics_lines=None):
        """Создает карточку в стиле Яндекс.Музыки с тремя строчками текста"""
        try:
            
            card_width = 600
            card_height = 1050
            margin = 30
            
            
            album_art_url = track_info['album_art']
            async with aiohttp.ClientSession() as session:
                async with session.get(album_art_url) as response:
                    art_data = await response.read()
                    album_art_original = Image.open(BytesIO(art_data))
            
            
            dominant_color = self._get_dominant_color(album_art_original)
            
            
            card = self._create_gradient_background(card_width, card_height, dominant_color)
            
            
            album_size = 300
            album_art = album_art_original.resize((album_size, album_size), Image.Resampling.LANCZOS)
            
            
            mask = Image.new('L', (album_size, album_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, album_size, album_size], radius=20, fill=255)
            album_art.putalpha(mask)
            
            
            art_x = (card_width - album_size) // 2
            art_y = 120
            card.paste(album_art, (art_x, art_y), album_art)
            
            draw = ImageDraw.Draw(card, "RGBA")
            
            
            font_paths = {
                'bold': None,
                'regular': None
            }
            
            font_candidates = [
                
                ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Helvetica.ttc"),
                ("/System/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Arial Bold.ttf"),
                
                ("arial.ttf", "arialbd.ttf"),
                ("calibri.ttf", "calibrib.ttf"),
                
                ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
                ("Liberation Sans", "Liberation Sans Bold"),
                
                (None, None)
            ]
            
            for regular, bold in font_candidates:
                try:
                    if regular:
                        test_font = ImageFont.truetype(regular, 18)
                        temp_img = Image.new('RGB', (10, 10))
                        temp_draw = ImageDraw.Draw(temp_img)
                        temp_draw.text((0, 0), "Test Тест", font=test_font, fill='white')
                        
                        font_paths['regular'] = regular
                        font_paths['bold'] = bold if bold else regular
                        break
                except:
                    continue
            
            
            track_name = str(track_info['track_name'])
            track_name = track_name.encode('utf-8', errors='ignore').decode('utf-8')
            
            max_title_width = card_width - (margin * 2)
            title_font = self._get_optimal_font_size(
                track_name, max_title_width, 60, font_paths['bold'], 36
            )
            
            title_lines = self._wrap_text(track_name, max_title_width, title_font, draw)
            
            title_y = art_y + album_size + 45
            for i, line in enumerate(title_lines[:2]):
                try:
                    line_bbox = draw.textbbox((0, 0), line, font=title_font)
                    line_width = line_bbox[2] - line_bbox[0]
                    line_x = (card_width - line_width) // 2
                    current_y = title_y + i * 45
                    draw.text((line_x, current_y), line, font=title_font, fill='white')
                except Exception as e:
                    logger.debug(f"Error drawing title line: {e}")
                    draw.text((margin, current_y), line, font=title_font, fill='white')
            
            
            artist_name = str(track_info['artist_name'])  
            artist_name = artist_name.encode('utf-8', errors='ignore').decode('utf-8')
            
            max_artist_width = card_width - (margin * 2)
            artist_font = self._get_optimal_font_size(
                artist_name, max_artist_width, 45, font_paths['regular'], 28
            )
            
            artist_lines = self._wrap_text(artist_name, max_artist_width, artist_font, draw)
            artist_y = title_y + (len(title_lines) * 45) + 15
            
            for i, line in enumerate(artist_lines[:1]):
                try:
                    line_bbox = draw.textbbox((0, 0), line, font=artist_font)
                    line_width = line_bbox[2] - line_bbox[0]
                    line_x = (card_width - line_width) // 2
                    current_y = artist_y + i * 35
                    draw.text((line_x, current_y), line, font=artist_font, fill='#B8B8B8')
                except Exception as e:
                    logger.debug(f"Error drawing artist line: {e}")
                    draw.text((margin, current_y), line, font=artist_font, fill='#B8B8B8')
            
            
            if lyrics_lines:
                lyrics_start_y = artist_y + 75
                max_lyrics_width = card_width - (margin * 2)
                
                available_height = card_height - lyrics_start_y - 150
                line_height = min(50, available_height // 3)
                
                for i, line in enumerate(lyrics_lines[:3]):
                    if line and line.strip():
                        line = str(line).encode('utf-8', errors='ignore').decode('utf-8')
                        
                        lyrics_font = self._get_optimal_font_size(
                            line, max_lyrics_width, line_height - 8, font_paths['regular'], 30
                        )
                        
                        wrapped_lines = self._wrap_text(line, max_lyrics_width, lyrics_font, draw)
                        display_line = wrapped_lines[0] if wrapped_lines else line
                        
                        try:
                            line_bbox = draw.textbbox((0, 0), display_line, font=lyrics_font)
                            line_width = line_bbox[2] - line_bbox[0]
                            line_x = (card_width - line_width) // 2
                            line_y = lyrics_start_y + i * line_height
                            
                            
                            if i == 0:
                                draw.text((line_x, line_y), display_line, font=lyrics_font, fill='white')
                            else:
                                draw.text((line_x, line_y), display_line, font=lyrics_font, fill='#A0A0A0')
                        except Exception as e:
                            logger.debug(f"Error drawing lyrics line: {e}")
                            line_y = lyrics_start_y + i * line_height
                            if i == 0:
                                draw.text((margin, line_y), display_line, font=lyrics_font, fill='white')
                            else:
                                draw.text((margin, line_y), display_line, font=lyrics_font, fill='#A0A0A0')
            
            
            yamusic_text = "ЯНДЕКС МУЗЫКА"
            small_font = self._get_optimal_font_size(
                yamusic_text, card_width - (margin * 4), 30, font_paths['regular'], 22
            )
            
            try:
                yamusic_bbox = draw.textbbox((0, 0), yamusic_text, font=small_font)
                yamusic_width = yamusic_bbox[2] - yamusic_bbox[0]
                yamusic_x = (card_width - yamusic_width) // 2
                yamusic_y = card_height - 75
                
                
                draw.text((yamusic_x, yamusic_y), yamusic_text, font=small_font, fill='#FFCC00')
                
                
                dot_radius = 3
                dot_y = yamusic_y + 10
                
                
                left_dot_x = yamusic_x - 30
                draw.ellipse([left_dot_x-dot_radius, dot_y-dot_radius, 
                             left_dot_x+dot_radius, dot_y+dot_radius], fill='#FFCC00')
                
                
                right_dot_x = yamusic_x + yamusic_width + 30
                draw.ellipse([right_dot_x-dot_radius, dot_y-dot_radius, 
                             right_dot_x+dot_radius, dot_y+dot_radius], fill='#FFCC00')
            except Exception as e:
                logger.debug(f"Error drawing Яндекс.Музыка logo: {e}")
                draw.text((card_width//2 - 60, card_height - 75), yamusic_text, font=small_font, fill='#FFCC00')
            
            
            card_path = os.path.join(tempfile.gettempdir(), f"yamusic_share_{track_info['track_id']}.png")
            card.save(card_path, "PNG", optimize=True, quality=95)
            
            return card_path
            
        except Exception as e:
            logger.error(f"Error creating Яндекс.Музыка share card: {e}")
            return None

    @loader.command()
    async def yshare(self, message):
        """Поделиться текущим треком в стиле Яндекс.Музыки"""
        
        yamusic_module = self._get_yamusic_module()
        if not yamusic_module:
            return await utils.answer(message, self.strings['no_yamusic_module'])

        
        token = self._get_yamusic_token()
        if not token:
            return await utils.answer(message, self.strings['no_auth_token'])

        try:
            client = yandex_music.Client(token).init()
            
            
            now = await yamusic_module._YaMusicMod__get_now_playing(token, client)
            
            if not now or now.get('paused', True):
                return await utils.answer(message, self.strings['no_song_playing'])

            await utils.answer(message, self.strings['track_loading'])

            track_info = now['track']
            track_name = track_info['title']
            artist_name = ", ".join(track_info['artist'])
            track_id = track_info['track_id']

            
            lyrics_lines = await self._get_lyrics_from_yamusic(client, track_id)

            
            card_track_info = {
                'track_name': track_name,
                'artist_name': artist_name,
                'album_art': track_info['img'],
                'track_id': track_id
            }

            
            card_path = await self._create_yamusic_share_card(card_track_info, lyrics_lines)

            if card_path:
                await self._client.send_file(
                    message.chat_id,
                    card_path,
                    reply_to=message.reply_to_msg_id if message.is_reply else getattr(message, "top_id", None)
                )
                
                
                try:
                    os.remove(card_path)
                except:
                    pass
            else:
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(track_info['img']) as response:
                        art_data = await response.read()
                
                caption = f"🎵 <b>{track_name}</b>\n👤 <b>{artist_name}</b>"
                if lyrics_lines and lyrics_lines[0]:
                    caption += f"\n\n📝 <i>{lyrics_lines[0]}</i>"
                        
                await self._client.send_file(
                    message.chat_id,
                    art_data,
                    caption=caption,
                    reply_to=message.reply_to_msg_id if message.is_reply else getattr(message, "top_id", None)
                )

            await message.delete()

        except yandex_music.exceptions.UnauthorizedError:
            return await utils.answer(message, self.strings['no_auth_token'])
        except Exception as e:
            logger.error(f"Error in yshare: {e}")
            return await utils.answer(message, self.strings['unexpected_error'].format(str(e)))
