# ©️ LoLpryvet, 2025
# 🌐 https://github.com/lolpryvetik/Modules/blob/main/Spots.py
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

# ---------------------------------------------------------------------------------
# Name: Spots
# Description: Слушай музыку в Spotify
# meta developer: @LoLpryvet
# requires: spotipy aiohttp pillow
# ---------------------------------------------------------------------------------

import asyncio
import logging
import tempfile
import aiohttp
import os
import re
from io import BytesIO

import spotipy
from PIL import Image, ImageDraw, ImageFont, ImageStat
import colorsys

from telethon import types

from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class Spots(loader.Module):
    """Слушай музыку в Spotify"""

    strings = {
        "name": "Spots",

        "go_auth_link": """<b><emoji document_id=5271604874419647061>🔗</emoji> Ссылка для авторизации создана!
        
🔐 Перейди по <a href='{}'>этой ссылке</a>.
        
✏️ Потом введи: <code>{}spcode свой_auth_token</code></b>""",

        "need_client_tokens": """<emoji document_id=5472308992514464048>🔐</emoji> <b>Создай приложение по <a href="https://developer.spotify.com/dashboard">этой ссылке</a></b>

<emoji document_id=5467890025217661107>‼️</emoji> <b>Важно:</b> redirect_url приложения должен быть <code>https://sp.fajox.one</code>
        
<b><emoji document_id=5330115548900501467>🔑</emoji> Заполни <code>client_id</code> и <code>client_secret</code> в <code>{}cfg Spots</code></b>

<b><emoji document_id=5431376038628171216>💻</emoji> И снова напиши <code>{}spauth</code></b>""",

        "no_auth_token": "<emoji document_id=5854929766146118183>❌</emoji> <b>Авторизуйся в свой аккаунт через <code>{}spauth</code></b>",
        "no_song_playing": "<emoji document_id=5854929766146118183>❌</emoji> <b>Сейчас ничего не играет.</b>",
        "no_code": "<emoji document_id=5854929766146118183>❌</emoji> <b>Должно быть <code>{}spcode код_авторизации</code></b>",
        "code_installed": """<b><emoji document_id=5330115548900501467>🔑</emoji> Код авторизации установлен!</b>
        
<emoji document_id=5870794890006237381>🎶</emoji> <b>Наслаждайся музыкой!</b>""",

        "auth_error": "<emoji document_id=5854929766146118183>❌</emoji> <b>Ошибка авторизации:</b> <code>{}</code>",
        "unexpected_error": "<emoji document_id=5854929766146118183>❌</emoji> <b>Произошла ошибка:</b> <code>{}</code>",

        "track_loading": "<emoji document_id=5334768819548200731>💻</emoji> <b>Загружаю трек...</b>",
        "lyrics_loading": "<emoji document_id=5334768819548200731>💻</emoji> <b>Ищу текст песни...</b>",
        
        "lyrics": (
            "<emoji document_id=5956561916573782596>📜</emoji> <b>Текст трека "
            "<a href=\"{track_url}\">{artist} — {title}</a>:</b>\n"
            "<blockquote expandable>{text}</blockquote>"
        ),
        "synced_lyrics": (
            "<emoji document_id=5956561916573782596>📜</emoji> <b>Текст трека "
            "<a href=\"{track_url}\">{artist} — {title}</a>:</b>\n"
            "<blockquote expandable>{text}</blockquote>"
        ),
        "no_lyrics": (
            "<emoji document_id=5886285363869126932>❌</emoji> <b>Текст для трека "
            "<a href=\"{track_url}\">{artist} — {title}</a> не найден!</b>"
        ),
        "no_synced_lyrics": (
            "<emoji document_id=5886285363869126932>❌</emoji> <b>Синхронизированный текст для трека "
            "<a href=\"{track_url}\">{artist} — {title}</a> не найден!</b>\n\n"
            "<i>Попробуйте команду <code>{prefix}lyrics</code> для поиска обычного текста.</i>"
        ),
        "realtime_stopped": "✅ <b>Обновление текста в реальном времени остановлено</b>",
        "no_realtime_active": "❌ <b>Сеанс синхронизации не активен</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "client_id",
                None,
                lambda: "Айди приложения, Получить: https://developer.spotify.com/dashboard",
                validator=loader.validators.Hidden(loader.validators.String()),
            ),
            loader.ConfigValue(
                "client_secret",
                None,
                lambda: "Секретный ключ приложения, Получить: https://developer.spotify.com/dashboard",
                validator=loader.validators.Hidden(loader.validators.String()),
            ),
            loader.ConfigValue(
                "auth_token",
                None,
                lambda: "Токен для авторизации",
                validator=loader.validators.Hidden(loader.validators.String()),
            ),
            loader.ConfigValue(
                "refresh_token",
                None,
                lambda: "Токен для обновления",
                validator=loader.validators.Hidden(loader.validators.String()),
            ),
            loader.ConfigValue(
                "scopes",
                "user-read-playback-state user-library-read",
                lambda: "Список разрешений",
            ),
            loader.ConfigValue(
                "genius_token",
                None,
                lambda: "Токен Genius API для получения текстов (получить: https://genius.com/api-clients)",
                validator=loader.validators.Hidden(loader.validators.String()),
            ),
        )

    async def client_ready(self, client, db):
        self.db = db
        self._client = client

        self.musicdl = await self.import_lib(
            "https://famods.fajox.one/assets/musicdl.py",
            suspend_on_error=True,
        )

    async def _get_lyrics_from_lrclib(self, artist, title, duration_ms=None):
        """Получает синхронизированный текст песни через LRCLib API"""
        try:
            
            clean_title = re.sub(r'\([^)]*\)', '', title).strip()
            clean_artist = re.sub(r'\([^)]*\)', '', artist).strip()
            
            
            params = {
                'artist_name': clean_artist,
                'track_name': clean_title
            }
            
            
            if duration_ms:
                params['duration'] = duration_ms // 1000
            
            url = "https://lrclib.net/api/search"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            
                            track_data = data[0]
                            
                            
                            synced_lyrics = track_data.get('syncedLyrics')
                            plain_lyrics = track_data.get('plainLyrics')
                            
                            if synced_lyrics:
                                
                                return {
                                    'type': 'synced',
                                    'lyrics': synced_lyrics,
                                    'plain': plain_lyrics
                                }
                            elif plain_lyrics:
                                
                                return {
                                    'type': 'plain',
                                    'lyrics': plain_lyrics
                                }
                    
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting lyrics from LRCLib: {e}")
            return None

    async def _get_lyrics_from_genius(self, artist, title):
        """Получает текст песни через Genius API"""
        if not self.config['genius_token']:
            return None
            
        try:
            
            clean_title = re.sub(r'\([^)]*\)', '', title).strip()
            clean_artist = re.sub(r'\([^)]*\)', '', artist).strip()
            
            
            search_url = "https://api.genius.com/search"
            headers = {"Authorization": f"Bearer {self.config['genius_token']}"}
            params = {"q": f"{clean_artist} {clean_title}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, params=params) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    hits = data.get('response', {}).get('hits', [])
                    
                    if not hits:
                        return None
                    
                    
                    song_url = None
                    for hit in hits:
                        song = hit.get('result', {})
                        song_title = song.get('title', '').lower()
                        song_artist = song.get('primary_artist', {}).get('name', '').lower()
                        
                        if (clean_title.lower() in song_title or song_title in clean_title.lower()) and \
                           (clean_artist.lower() in song_artist or song_artist in clean_artist.lower()):
                            song_url = song.get('url')
                            break
                    
                    if not song_url:
                        song_url = hits[0].get('result', {}).get('url')
                    
                    if not song_url:
                        return None
                    
                    
                    return await self._scrape_genius_lyrics(song_url)
                    
        except Exception as e:
            logger.error(f"Error getting lyrics from Genius: {e}")
            return None

    async def _scrape_genius_lyrics(self, url):
        """Парсит текст с веб-страницы Genius"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    
                    
                    import re
                    
                    
                    lyrics_pattern = r'<div[^>]*data-lyrics-container="true"[^>]*>(.*?)</div>'
                    matches = re.findall(lyrics_pattern, html, re.DOTALL | re.IGNORECASE)
                    
                    if not matches:
                        
                        lyrics_pattern = r'<div[^>]*class="[^"]*lyrics[^"]*"[^>]*>(.*?)</div>'
                        matches = re.findall(lyrics_pattern, html, re.DOTALL | re.IGNORECASE)
                    
                    if matches:
                        
                        lyrics = matches[0]
                        lyrics = re.sub(r'<br[^>]*>', '\n', lyrics)
                        lyrics = re.sub(r'<[^>]+>', '', lyrics)
                        lyrics = lyrics.strip()
                        
                        
                        lyrics = lyrics.replace('&amp;', '&')
                        lyrics = lyrics.replace('&lt;', '<')
                        lyrics = lyrics.replace('&gt;', '>')
                        lyrics = lyrics.replace('&quot;', '"')
                        lyrics = lyrics.replace('&#x27;', "'")
                        
                        return lyrics if lyrics else None
                    
                    return None
                    
        except Exception as e:
            logger.error(f"Error scraping Genius lyrics: {e}")
            return None

    async def _get_lyrics_from_api(self, artist, title):
        """Получает текст песни через бесплатный API lyrics.ovh"""
        try:
            url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        lyrics = data.get('lyrics')
                        if lyrics:
                            return {
                                'type': 'plain',
                                'lyrics': lyrics
                            }
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting lyrics from lyrics.ovh: {e}")
            return None

    def _format_synced_lyrics(self, synced_lyrics, current_progress_ms=None):
        """Форматирует синхронизированные тексты для отображения"""
        if not synced_lyrics:
            return None
            
        lines = synced_lyrics.strip().split('\n')
        formatted_lines = []
        current_line_found = False
        
        for line in lines:
            
            time_match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2})\](.*)', line)
            if time_match:
                minutes = int(time_match.group(1))
                seconds = int(time_match.group(2))
                centiseconds = int(time_match.group(3))
                text = time_match.group(4).strip()
                
                
                line_time_ms = (minutes * 60 + seconds) * 1000 + centiseconds * 10
                
                
                if current_progress_ms and not current_line_found:
                    if line_time_ms <= current_progress_ms:
                        
                        next_line_time = None
                        line_index = lines.index(line)
                        if line_index + 1 < len(lines):
                            next_match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2})\]', lines[line_index + 1])
                            if next_match:
                                next_minutes = int(next_match.group(1))
                                next_seconds = int(next_match.group(2))
                                next_centiseconds = int(next_match.group(3))
                                next_line_time = (next_minutes * 60 + next_seconds) * 1000 + next_centiseconds * 10
                        
                        if next_line_time is None or current_progress_ms < next_line_time:
                            
                            formatted_lines.append(f"<b>→ {text}</b>")
                            current_line_found = True
                        else:
                            formatted_lines.append(text)
                    else:
                        formatted_lines.append(text)
                else:
                    formatted_lines.append(text)
            else:
                
                if line.strip():
                    formatted_lines.append(line.strip())
        
        return '\n'.join(formatted_lines)

    async def _get_synced_lyrics_data(self, artist, title, duration_ms=None):
        """Получает синхронизированные данные текста песни с временными метками"""
        try:
            
            clean_title = re.sub(r'\([^)]*\)', '', title).strip()
            clean_artist = re.sub(r'\([^)]*\)', '', artist).strip()
            
            
            params = {
                'artist_name': clean_artist,
                'track_name': clean_title
            }
            
            
            if duration_ms:
                params['duration'] = duration_ms // 1000
            
            url = "https://lrclib.net/api/search"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            track_data = data[0]
                            synced_lyrics = track_data.get('syncedLyrics')
                            
                            if synced_lyrics:
                                
                                return self._parse_synced_lyrics(synced_lyrics)
                    
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting synced lyrics from LRCLib: {e}")
            return None

    def _parse_synced_lyrics(self, synced_lyrics):
        """Парсит синхронизированные тексты в список с временными метками"""
        if not synced_lyrics:
            return None
            
        lines = synced_lyrics.strip().split('\n')
        parsed_lines = []
        
        for line in lines:
            
            time_match = re.match(r'\[(\d{2}):(\d{2})\.(\d{2})\](.*)', line)
            if time_match:
                minutes = int(time_match.group(1))
                seconds = int(time_match.group(2))
                centiseconds = int(time_match.group(3))
                text = time_match.group(4).strip()
                
                
                time_ms = (minutes * 60 + seconds) * 1000 + centiseconds * 10
                
                if text:  
                    parsed_lines.append({
                        'time_ms': time_ms,
                        'text': text,
                        'timestamp': f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
                    })
        
        return parsed_lines

    def _get_current_lyric_line(self, lyrics_data, current_progress_ms):
        """Находит текущую строку текста на основе прогресса воспроизведения"""
        if not lyrics_data:
            return None, -1
            
        current_line = None
        current_index = -1
        
        for i, line in enumerate(lyrics_data):
            if line['time_ms'] <= current_progress_ms:
                
                if i + 1 < len(lyrics_data):
                    next_line = lyrics_data[i + 1]
                    if current_progress_ms < next_line['time_ms']:
                        current_line = line
                        current_index = i
                        break
                else:
                    
                    current_line = line
                    current_index = i
                    break
        
        return current_line, current_index

    def _format_realtime_lyrics(self, lyrics_data, current_index, context_lines=2):
        """Форматирует текст для отображения с выделением текущей строки"""
        if not lyrics_data or current_index == -1:
            return "🎵 Ожидание синхронизации..."
            
        formatted_lines = []
        
        
        start_index = max(0, current_index - context_lines)
        end_index = min(len(lyrics_data), current_index + context_lines + 1)
        
        for i in range(start_index, end_index):
            line = lyrics_data[i]
            if i == current_index:
                
                formatted_lines.append(f"<b>▶️ {line['text']}</b>")
            elif i < current_index:
                
                formatted_lines.append(f"<i>{line['text']}</i>")
            else:
                
                formatted_lines.append(line['text'])
        
        return '\n'.join(formatted_lines)

    async def _realtime_lyrics_loop(self):
        """Цикл обновления текста в реальном времени"""
        if not hasattr(self, '_realtime_lyrics_data') or not self._realtime_lyrics_data['active']:
            return
            
        try:
            data = self._realtime_lyrics_data
            update_count = 0
            max_updates = 600  
            pause_count = 0  
            max_pause_time = 120  
            last_pause_message_count = -1  
            
            while data['active'] and update_count < max_updates:
                try:
                    
                    sp = spotipy.Spotify(auth=self.config['auth_token'])
                    current_playback = sp.current_playback()
                    
                    if not current_playback or not current_playback.get('item'):
                        
                        pause_count += 1
                        if pause_count > 30:  
                            break
                        
                        await asyncio.sleep(1)
                        update_count += 1
                        continue
                    
                    current_track_id = current_playback['item'].get('id', '')
                    if current_track_id != data['track_id']:
                        
                        break
                    
                    progress_ms = current_playback.get('progress_ms', 0)
                    is_playing = current_playback.get('is_playing', False)
                    
                    if not is_playing:
                        
                        pause_count += 1
                        
                        
                        if pause_count >= max_pause_time:
                            new_text = data['header'] + "⏸️ <i>Сеанс завершен из-за длительной паузы</i>"
                            try:
                                await self._client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    new_text,
                                    parse_mode='html'
                                )
                            except:
                                pass
                            break
                        
                       
                        if last_pause_message_count == -1 or pause_count - last_pause_message_count >= 10:
                            new_text = data['header'] + "⏸️ <i>Воспроизведение приостановлено</i>"
                            try:
                                await self._client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    new_text,
                                    parse_mode='html'
                                )
                                last_pause_message_count = pause_count
                            except Exception as edit_error:
                                logger.debug(f"Failed to edit pause message: {edit_error}")
                        
                        
                        await asyncio.sleep(1)
                        update_count += 1
                        continue
                        
                    else:
                        
                        if pause_count > 0:
                            pause_count = 0
                            last_pause_message_count = -1
                        
                        
                        current_line, current_index = self._get_current_lyric_line(data['lyrics_data'], progress_ms)
                        
                        
                        if current_index != data['last_line_index']:
                            formatted_lyrics = self._format_realtime_lyrics(data['lyrics_data'], current_index)
                            new_text = data['header'] + formatted_lyrics
                            data['last_line_index'] = current_index
                            
                            
                            try:
                                await self._client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    new_text,
                                    parse_mode='html'
                                )
                            except Exception as edit_error:
                                
                                logger.debug(f"Failed to edit message: {edit_error}")
                                break
                    
                    
                    await asyncio.sleep(1)
                    update_count += 1
                    
                except spotipy.exceptions.SpotifyException as e:
                    
                    logger.debug(f"Spotify API error: {e}")
                    await asyncio.sleep(3)
                    update_count += 1
                    continue
                except Exception as e:
                    logger.error(f"Error in realtime lyrics loop: {e}")
                    await asyncio.sleep(2)  
                    update_count += 1
            
            
            data['active'] = False
            
            
            try:
                final_text = data['header'] + "✅ <i>Сеанс синхронизации завершен</i>"
                await self._client.edit_message(
                    data['chat_id'],
                    data['message_id'],
                    final_text,
                    parse_mode='html'
                )
            except:
                pass
                
        except Exception as e:
            logger.error(f"Critical error in realtime lyrics loop: {e}")
            if hasattr(self, '_realtime_lyrics_data'):
                self._realtime_lyrics_data['active'] = False

    async def _create_song_card(self, track_info):
        """Создаёт красивую карточку с песней с адаптивным цветом фона"""
        try:
            
            card_width = 800
            card_height = 300
            
            
            album_art_url = track_info['album_art']
            async with aiohttp.ClientSession() as session:
                async with session.get(album_art_url) as response:
                    art_data = await response.read()
                    album_art_original = Image.open(BytesIO(art_data))
            
            def get_dominant_color(image):
                """Получает доминирующий цвет изображения"""
                
                small_image = image.resize((50, 50))
                stat = ImageStat.Stat(small_image)
                # Получаем средние значения RGB
                r, g, b = stat.mean
                return int(r), int(g), int(b)
            
            def create_darker_variant(r, g, b, factor=0.4):
                """Создает более темный вариант цвета"""
                
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                
                v = max(0.15, v * factor)
                s = min(1.0, s * 1.1)
                
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                return int(r * 255), int(g * 255), int(b * 255)
            
            
            dominant_r, dominant_g, dominant_b = get_dominant_color(album_art_original)
            
            
            bg_r, bg_g, bg_b = create_darker_variant(dominant_r, dominant_g, dominant_b)
            
            
            card = Image.new('RGB', (card_width, card_height), color=(bg_r, bg_g, bg_b))
            draw = ImageDraw.Draw(card)
            
            
            center_x = 150  
            center_y = card_height // 2
            max_distance = max(card_width, card_height)
            
            for x in range(card_width):
                for y in range(card_height):
                    
                    distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                    
                    factor = min(1.0, distance / max_distance)
                    
                    
                    final_r = int(bg_r + (bg_r * 0.2 - bg_r) * factor)
                    final_g = int(bg_g + (bg_g * 0.2 - bg_g) * factor)
                    final_b = int(bg_b + (bg_b * 0.2 - bg_b) * factor)
                    
                    
                    final_r = max(0, min(255, final_r))
                    final_g = max(0, min(255, final_g))
                    final_b = max(0, min(255, final_b))
                    
                    
                    card.putpixel((x, y), (final_r, final_g, final_b))
            
            
            album_size = 240
            album_art = album_art_original.resize((album_size, album_size), Image.Resampling.LANCZOS)
            
            
            mask = Image.new('L', (album_size, album_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, album_size, album_size], radius=20, fill=255)
            
            
            album_art.putalpha(mask)
            
            
            art_x = 30
            art_y = int((card_height - album_size) // 2)  
            card.paste(album_art, (art_x, art_y), album_art)
            
            
            try:
                
                title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica-Bold.ttc", 42)
                artist_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
                time_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
            except:
                try:
                    title_font = ImageFont.truetype("arial.ttf", 42)
                    artist_font = ImageFont.truetype("arial.ttf", 28)
                    time_font = ImageFont.truetype("arial.ttf", 20)
                except:
                    try:
                        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
                        artist_font = ImageFont.truetype("DejaVuSans.ttf", 28)
                        time_font = ImageFont.truetype("DejaVuSans.ttf", 20)
                    except:
                        title_font = ImageFont.load_default()
                        artist_font = ImageFont.load_default()
                        time_font = ImageFont.load_default()
            
            
            text_x = art_x + album_size + 30
            
            
            track_name = track_info['track_name']
            if len(track_name) > 20:
                track_name = track_name[:20] + "..."
            draw.text((text_x, 60), track_name, font=title_font, fill='white')
            
            
            artist_name = track_info['artist_name']
            if len(artist_name) > 25:
                artist_name = artist_name[:25] + "..."
            draw.text((text_x, 110), artist_name, font=artist_font, fill='#A0A0A0')
            
            
            progress_y = 220
            progress_width = card_width - text_x - 30  
            progress_height = 6
            progress_x = text_x
            
            
            draw.rounded_rectangle([progress_x, progress_y, progress_x + progress_width, progress_y + progress_height], 
                                 radius=3, fill='#555555')
            
            
            current_time_str = track_info.get('current_time', '00:17')
            duration_str = track_info['duration']
            
            
            try:
                current_parts = current_time_str.split(':')
                current_seconds = int(current_parts[0]) * 60 + int(current_parts[1])
                
                duration_parts = duration_str.split(':')
                duration_seconds = int(duration_parts[0]) * 60 + int(duration_parts[1])
                
                if duration_seconds > 0:
                    progress_ratio = current_seconds / duration_seconds
                else:
                    progress_ratio = 0.1
            except:
                progress_ratio = 0.1
            
            progress_fill = int(progress_width * progress_ratio)
            draw.rounded_rectangle([progress_x, progress_y, progress_x + progress_fill, progress_y + progress_height], 
                                 radius=3, fill='white')
            
            
            current_time = track_info.get('current_time', '00:17')
            total_time = track_info['duration']
            
            
            draw.text((progress_x, progress_y + 20), current_time, font=time_font, fill='#A0A0A0')
            
            
            time_bbox = draw.textbbox((0, 0), total_time, font=time_font)
            time_width = time_bbox[2] - time_bbox[0]
            draw.text((progress_x + progress_width - time_width, progress_y + 20), total_time, 
                     font=time_font, fill='#A0A0A0')
            
            
            card_path = os.path.join(tempfile.gettempdir(), f"spots_card_{track_info['track_id']}.png")
            card.save(card_path, "PNG")
            
            return card_path
            
        except Exception as e:
            logger.error(f"Error creating song card: {e}")
            return None

    async def _create_song_card_no_time(self, track_info):
        """Создаёт красивую карточку с песней без отображения времени"""
        try:
            
            card_width = 800
            card_height = 250  
            
            
            album_art_url = track_info['album_art']
            async with aiohttp.ClientSession() as session:
                async with session.get(album_art_url) as response:
                    art_data = await response.read()
                    album_art_original = Image.open(BytesIO(art_data))
            
            
            def get_dominant_color(image):
                """Получает доминирующий цвет изображения"""
                small_image = image.resize((50, 50))
                stat = ImageStat.Stat(small_image)
                r, g, b = stat.mean
                return int(r), int(g), int(b)
            
            def create_darker_variant(r, g, b, factor=0.4):
                """Создает более темный вариант цвета"""
                h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                v = max(0.15, v * factor)
                s = min(1.0, s * 1.1)
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                return int(r * 255), int(g * 255), int(b * 255)
            
            
            dominant_r, dominant_g, dominant_b = get_dominant_color(album_art_original)
            
            
            bg_r, bg_g, bg_b = create_darker_variant(dominant_r, dominant_g, dominant_b)
            
            
            card = Image.new('RGB', (card_width, card_height), color=(bg_r, bg_g, bg_b))
            draw = ImageDraw.Draw(card)
            
            
            center_x = 125  
            center_y = card_height // 2
            max_distance = max(card_width, card_height)
            
            for x in range(card_width):
                for y in range(card_height):
                    
                    distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                    
                    factor = min(1.0, distance / max_distance)
                    
                    
                    final_r = int(bg_r + (bg_r * 0.2 - bg_r) * factor)
                    final_g = int(bg_g + (bg_g * 0.2 - bg_g) * factor)
                    final_b = int(bg_b + (bg_b * 0.2 - bg_b) * factor)
                    
                    
                    final_r = max(0, min(255, final_r))
                    final_g = max(0, min(255, final_g))
                    final_b = max(0, min(255, final_b))
                    
                    
                    card.putpixel((x, y), (final_r, final_g, final_b))
            
            
            album_size = 200  
            album_art = album_art_original.resize((album_size, album_size), Image.Resampling.LANCZOS)
            
            
            mask = Image.new('L', (album_size, album_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, album_size, album_size], radius=20, fill=255)
            
            
            album_art.putalpha(mask)
            
            
            art_x = 25
            art_y = int((card_height - album_size) // 2)  
            card.paste(album_art, (art_x, art_y), album_art)
            
            
            try:
                title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica-Bold.ttc", 42)
                artist_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
            except:
                try:
                    title_font = ImageFont.truetype("arial.ttf", 42)
                    artist_font = ImageFont.truetype("arial.ttf", 28)
                except:
                    try:
                        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
                        artist_font = ImageFont.truetype("DejaVuSans.ttf", 28)
                    except:
                        title_font = ImageFont.load_default()
                        artist_font = ImageFont.load_default()
            
            
            text_x = art_x + album_size + 30
            
            
            track_name = track_info['track_name']
            if len(track_name) > 20:
                track_name = track_name[:20] + "..."
            
            
            title_y = card_height // 2 - 30
            artist_y = card_height // 2 + 10
            
            draw.text((text_x, title_y), track_name, font=title_font, fill='white')
            
            
            artist_name = track_info['artist_name']
            if len(artist_name) > 25:
                artist_name = artist_name[:25] + "..."
            draw.text((text_x, artist_y), artist_name, font=artist_font, fill='#A0A0A0')
            
            
            live_indicator_x = card_width - 80
            live_indicator_y = 20
            
            
            draw.ellipse([live_indicator_x, live_indicator_y, live_indicator_x + 12, live_indicator_y + 12], fill='#FF0000')
            draw.text((live_indicator_x + 20, live_indicator_y - 3), "LIVE", font=artist_font, fill='#FF0000')
            
            
            card_path = os.path.join(tempfile.gettempdir(), f"playnow_card_{track_info['track_id']}.png")
            card.save(card_path, "PNG")
            
            return card_path
            
        except Exception as e:
            logger.error(f"Error creating song card without time: {e}")
            return None

    async def _playnow_loop(self):
        """Цикл обновления карточки и текста в реальном времени"""
        if not hasattr(self, '_playnow_data') or not self._playnow_data['active']:
            return
            
        try:
            data = self._playnow_data
            update_count = 0
            max_updates = 1200  
            pause_count = 0
            max_pause_time = 120  
            last_pause_message_count = -1
            current_track_id = data.get('current_track_id')
            
            while data['active'] and update_count < max_updates:
                try:
                    
                    sp = spotipy.Spotify(auth=self.config['auth_token'])
                    current_playback = sp.current_playback()
                    
                    if not current_playback or not current_playback.get('item'):
                        
                        pause_count += 1
                        if pause_count > 30: 
                            break
                        await asyncio.sleep(1)
                        update_count += 1
                        continue
                    
                    new_track_id = current_playback['item'].get('id', '')
                    progress_ms = current_playback.get('progress_ms', 0)
                    is_playing = current_playback.get('is_playing', False)
                    
                    
                    track_changed = new_track_id != current_track_id
                    
                    if track_changed:
                        
                        await self._update_playnow_for_new_track(data, current_playback)
                        current_track_id = new_track_id
                        data['current_track_id'] = new_track_id
                        pause_count = 0
                        last_pause_message_count = -1
                        continue
                    
                    if not is_playing:
                        
                        pause_count += 1
                        
                        if pause_count >= max_pause_time:
                            new_text = "⏸️ <i>Сеанс завершен из-за длительной паузы</i>"
                            try:
                                await self._client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    new_text,
                                    parse_mode='html'
                                )
                            except:
                                pass
                            break
                        
                        if last_pause_message_count == -1 or pause_count - last_pause_message_count >= 10:
                            formatted_lyrics = "⏸️ <i>Воспроизведение приостановлено</i>"
                            try:
                                await self._client.edit_message(
                                    data['chat_id'],
                                    data['message_id'],
                                    formatted_lyrics,
                                    parse_mode='html'
                                )
                                last_pause_message_count = pause_count
                            except Exception as edit_error:
                                logger.debug(f"Failed to edit pause message: {edit_error}")
                            
                        await asyncio.sleep(1)
                        update_count += 1
                        continue
                        
                    else:
                        
                        if pause_count > 0:
                            pause_count = 0
                            last_pause_message_count = -1
                        
                        
                        if data.get('lyrics_data'):
                            current_line, current_index = self._get_current_lyric_line(data['lyrics_data'], progress_ms)
                            
                            if current_index != data.get('last_line_index', -1):
                                formatted_lyrics = self._format_realtime_lyrics(data['lyrics_data'], current_index)
                                data['last_line_index'] = current_index
                                
                                try:
                                    await self._client.edit_message(
                                        data['chat_id'],
                                        data['message_id'],
                                        formatted_lyrics,
                                        parse_mode='html'
                                    )
                                except Exception as edit_error:
                                    logger.debug(f"Failed to edit message: {edit_error}")
                                    break
                    
                    await asyncio.sleep(1)
                    update_count += 1
                    
                except spotipy.exceptions.SpotifyException as e:
                    logger.debug(f"Spotify API error: {e}")
                    await asyncio.sleep(3)
                    update_count += 1
                    continue
                except Exception as e:
                    logger.error(f"Error in playnow loop: {e}")
                    await asyncio.sleep(2)
                    update_count += 1
            
            
            data['active'] = False
            
            try:
                final_text = "✅ <i>Сеанс live-отображения завершен</i>"
                await self._client.edit_message(
                    data['chat_id'],
                    data['message_id'],
                    final_text,
                    parse_mode='html'
                )
            except:
                pass
                
        except Exception as e:
            logger.error(f"Critical error in playnow loop: {e}")
            if hasattr(self, '_playnow_data'):
                self._playnow_data['active'] = False

    async def _update_playnow_for_new_track(self, data, current_playback):
        """Обновляет карточку и текст для нового трека"""
        try:
            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            track_url = track['external_urls']['spotify']
            duration_ms = track.get('duration_ms', 0)
            track_id = track.get('id', '')

            
            track_info = {
                'track_name': track_name,
                'artist_name': artist_name,
                'album_art': track['album']['images'][0]['url'],
                'track_id': track_id
            }

            card_path = await self._create_song_card_no_time(track_info)
            
            
            lyrics_data = await self._get_synced_lyrics_data(artist_name, track_name, duration_ms)
            
            if lyrics_data:
                initial_lyrics = "🎵 Ожидание синхронизации..."
                data['lyrics_data'] = lyrics_data
                data['last_line_index'] = -1
            else:
                initial_lyrics = f"❌ <i>Синхронизированный текст для трека не найден</i>\n\n<a href='{track_url}'>{artist_name} — {track_name}</a>"
                data['lyrics_data'] = None

            if card_path:
                
                try:
                    
                    await self._client.delete_messages(data['chat_id'], data['message_id'])
                except:
                    pass
                
                
                new_message = await self._client.send_file(
                    data['chat_id'],
                    card_path,
                    caption=initial_lyrics,
                    parse_mode='html'
                )
                
                
                data['message_id'] = new_message.id
                
                
                try:
                    os.remove(card_path)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error updating playnow for new track: {e}")

    @loader.command()
    async def lyrics(self, message):
        """Получить текст текущего трека"""
        if not self.config['auth_token']:
            return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))

        try:
            sp = spotipy.Spotify(auth=self.config['auth_token'])
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                return await utils.answer(message, self.strings['no_song_playing'])

            await utils.answer(message, self.strings['lyrics_loading'])

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            track_url = track['external_urls']['spotify']
            duration_ms = track.get('duration_ms', 0)
            progress_ms = current_playback.get('progress_ms', 0)

            
            lyrics_data = None
            
            
            lyrics_data = await self._get_lyrics_from_lrclib(artist_name, track_name, duration_ms)
            
            
            if not lyrics_data and self.config['genius_token']:
                genius_lyrics = await self._get_lyrics_from_genius(artist_name, track_name)
                if genius_lyrics:
                    lyrics_data = {
                        'type': 'plain',
                        'lyrics': genius_lyrics
                    }
            
            
            if not lyrics_data:
                lyrics_data = await self._get_lyrics_from_api(artist_name, track_name)

            if lyrics_data:
                if lyrics_data['type'] == 'synced':
                    
                    formatted_lyrics = self._format_synced_lyrics(lyrics_data['lyrics'], progress_ms)
                    
                    await utils.answer(
                        message, 
                        self.strings["synced_lyrics"].format(
                            track_url=track_url,
                            artist=artist_name,
                            title=track_name,
                            text=formatted_lyrics
                        )
                    )
                else:
                    
                    await utils.answer(
                        message, 
                        self.strings["lyrics"].format(
                            track_url=track_url,
                            artist=artist_name,
                            title=track_name,
                            text=lyrics_data['lyrics']
                        )
                    )
            else:
                await utils.answer(
                    message, 
                    self.strings["no_lyrics"].format(
                        track_url=track_url,
                        artist=artist_name,
                        title=track_name
                    )
                )

        except spotipy.oauth2.SpotifyOauthError as e:
            return await utils.answer(message, self.strings['auth_error'].format(str(e)))
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))
            if "NO_ACTIVE_DEVICE" in str(e):
                return await utils.answer(message, self.strings['no_song_playing'])
            return await utils.answer(message, self.strings['unexpected_error'].format(str(e)))

    @loader.command()
    async def spauth(self, message):
        """Войти в свой аккаунт"""
        if not self.config['client_id'] or not self.config['client_secret']:
            return await utils.answer(message, self.strings['need_client_tokens'].format(self.get_prefix(), self.get_prefix()))

        sp_oauth = spotipy.oauth2.SpotifyOAuth(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret'],
            redirect_uri="https://sp.fajox.one",
            scope=self.config['scopes']
        )

        auth_url = sp_oauth.get_authorize_url()

        await utils.answer(message, self.strings['go_auth_link'].format(auth_url, self.get_prefix()))

    @loader.command()
    async def spcode(self, message):
        """Ввести код авторизации"""
        if not self.config['client_id'] or not self.config['client_secret']:
            return await utils.answer(message, self.strings['need_client_tokens'].format(self.get_prefix()))
        code = utils.get_args_raw(message)
        if not code:
            return await utils.answer(message, self.strings['no_code'].format(self.get_prefix()))

        sp_oauth = spotipy.oauth2.SpotifyOAuth(
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret'],
            redirect_uri="https://sp.fajox.one",
            scope=self.config['scopes']
        )
        try:
            token_info = sp_oauth.get_access_token(code)
            self.config['auth_token'] = token_info['access_token']
            self.config['refresh_token'] = token_info['refresh_token']

            sp = spotipy.Spotify(auth=token_info['access_token'])
            current_playback = sp.current_playback()
            
            await utils.answer(message, self.strings['code_installed'])
        except spotipy.oauth2.SpotifyOauthError as e:
            return await utils.answer(message, self.strings['auth_error'].format(str(e)))
        except Exception as e:
            return await utils.answer(message, self.strings['unexpected_error'].format(str(e)))

    @loader.command()
    async def spnow(self, message):
        """Текущий трек"""
        if not self.config['auth_token']:
            return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))

        try:
            sp = spotipy.Spotify(auth=self.config['auth_token'])
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                return await utils.answer(message, self.strings['no_song_playing'])

            await utils.answer(message, self.strings['track_loading'])

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            album_name = track['album'].get('name', 'Unknown Album')
            duration_ms = track.get('duration_ms', 0)
            progress_ms = current_playback.get('progress_ms', 0)
            is_playing = current_playback.get('is_playing', False)

            duration_min, duration_sec = divmod(duration_ms // 1000, 60)
            progress_min, progress_sec = divmod(progress_ms // 1000, 60)

            playlist = current_playback.get('context', {}).get('uri', '').split(':')[-1] if current_playback.get('context') else None
            device_name = current_playback.get('device', {}).get('name', 'Unknown Device')+" "+current_playback.get('device', {}).get('type', '')
            device_type = current_playback.get('device', {}).get('type', 'unknown')

            user_profile = sp.current_user()
            user_name = user_profile['display_name']
            user_id = user_profile['id']

            track_url = track['external_urls']['spotify']
            user_url = f"https://open.spotify.com/user/{user_id}"
            playlist_url = f"https://open.spotify.com/playlist/{playlist}" if playlist else None

            track_info = (
                f"<b>🎧 Now Playing</b>\n\n"
                f"<b><emoji document_id=5188705588925702510>🎶</emoji> {track_name} - <code>{artist_name}</code>\n"
                f"<b><emoji document_id=5870794890006237381>💿</emoji> Album:</b> <code>{album_name}</code>\n\n"
                f"<b><emoji document_id=6007938409857815902>🎧</emoji> Device:</b> <code>{device_name}</code>\n"
                + (("<b><emoji document_id=5872863028428410654>❤️</emoji> From favorite tracks</b>\n" if "playlist/collection" in playlist_url else
                    f"<b><emoji document_id=5944809881029578897>📑</emoji> From Playlist:</b> <a href='{playlist_url}'>View</a>\n") if playlist else "")
                + f"\n<b><emoji document_id=5902449142575141204>🔗</emoji> Track URL:</b> <a href='{track_url}'>Open in Spotify</a>"
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                audio_path = await self.musicdl.dl(f"{artist_name} - {track_name}", only_document=True)

                album_art_url = track['album']['images'][0]['url']
                async with aiohttp.ClientSession() as session:
                    async with session.get(album_art_url) as response:
                        art_path = os.path.join(temp_dir, "cover.jpg")
                        with open(art_path, "wb") as f:
                            f.write(await response.read())

            await self._client.send_file(
                message.chat_id,
                audio_path,
                caption=track_info,
                attributes=[
                    types.DocumentAttributeAudio(
                        duration=duration_ms//1000,
                        title=track_name,
                        performer=artist_name
                    )
                ],
                thumb=art_path,
                reply_to=message.reply_to_msg_id if message.is_reply else getattr(message, "top_id", None)
            )

            await message.delete()

        except spotipy.oauth2.SpotifyOauthError as e:
            return await utils.answer(message, self.strings['auth_error'].format(str(e)))
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))
            if "NO_ACTIVE_DEVICE" in str(e):
                return await utils.answer(message, self.strings['no_song_playing'])
            return await utils.answer(message, self.strings['unexpected_error'].format(str(e)))

    @loader.command()
    async def now(self, message):
        """Красивая карточка с текущим треком"""
        if not self.config['auth_token']:
            return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))

        try:
            sp = spotipy.Spotify(auth=self.config['auth_token'])
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                return await utils.answer(message, self.strings['no_song_playing'])

            await utils.answer(message, self.strings['track_loading'])

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            album_name = track['album'].get('name', 'Unknown Album')
            duration_ms = track.get('duration_ms', 0)
            progress_ms = current_playback.get('progress_ms', 0)
            track_id = track.get('id', '')

            duration_min, duration_sec = divmod(duration_ms // 1000, 60)
            duration_str = f"{duration_min}:{duration_sec:02d}"
            
            progress_min, progress_sec = divmod(progress_ms // 1000, 60)
            progress_str = f"{progress_min}:{progress_sec:02d}"

            track_url = track['external_urls']['spotify']
            song_link_url = f"https://song.link/s/{track_id}"

            
            track_info = {
                'track_name': track_name,
                'artist_name': artist_name,
                'album_name': album_name,
                'duration': duration_str,
                'current_time': progress_str,
                'album_art': track['album']['images'][0]['url'],
                'track_id': track_id
            }

            
            card_path = await self._create_song_card(track_info)
            
            
            caption = f"🎵 | <a href='{track_url}'>Spotify</a> • <a href='{song_link_url}'>song.link</a>"

            if card_path:
                await self._client.send_file(
                    message.chat_id,
                    card_path,
                    caption=caption,
                    reply_to=message.reply_to_msg_id if message.is_reply else getattr(message, "top_id", None)
                )
                
                
                try:
                    os.remove(card_path)
                except:
                    pass
            else:
                
                album_art_url = track['album']['images'][0]['url']
                async with aiohttp.ClientSession() as session:
                    async with session.get(album_art_url) as response:
                        art_data = await response.read()
                        
                await self._client.send_file(
                    message.chat_id,
                    art_data,
                    caption=f"<b>🎧 {track_name}</b>\n<b>👤 {artist_name}</b>\n<b>💿 {album_name}</b>\n\n" + caption,
                    reply_to=message.reply_to_msg_id if message.is_reply else getattr(message, "top_id", None)
                )

            await message.delete()

        except spotipy.oauth2.SpotifyOauthError as e:
            return await utils.answer(message, self.strings['auth_error'].format(str(e)))
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))
            if "NO_ACTIVE_DEVICE" in str(e):
                return await utils.answer(message, self.strings['no_song_playing'])
            return await utils.answer(message, self.strings['unexpected_error'].format(str(e)))

    @loader.command()
    async def rlyrics(self, message):
        """Показать текст текущего трека в реальном времени"""
        if not self.config['auth_token']:
            return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))

        try:
            sp = spotipy.Spotify(auth=self.config['auth_token'])
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                return await utils.answer(message, self.strings['no_song_playing'])

            await utils.answer(message, self.strings['lyrics_loading'])

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            track_url = track['external_urls']['spotify']
            duration_ms = track.get('duration_ms', 0)
            track_id = track.get('id', '')

            
            lyrics_data = await self._get_synced_lyrics_data(artist_name, track_name, duration_ms)
            
            if not lyrics_data:
                return await utils.answer(
                    message, 
                    self.strings["no_synced_lyrics"].format(
                        track_url=track_url,
                        artist=artist_name,
                        title=track_name,
                        prefix=self.get_prefix()
                    )
                )

            
            header = (
                f"<emoji document_id=5956561916573782596>📜</emoji> <b>Текст в реальном времени</b>\n"
                f"<a href=\"{track_url}\">{artist_name} — {track_name}</a>\n\n"
            )
            
            initial_text = header + "🎵 Ожидание синхронизации..."
            sent_message = await utils.answer(message, initial_text)
            
            
            self._realtime_lyrics_data = {
                'message_id': sent_message.id,
                'chat_id': message.chat_id,
                'lyrics_data': lyrics_data,
                'track_id': track_id,
                'header': header,
                'last_line_index': -1,
                'active': True
            }
            
            
            asyncio.create_task(self._realtime_lyrics_loop())

        except spotipy.oauth2.SpotifyOauthError as e:
            return await utils.answer(message, self.strings['auth_error'].format(str(e)))
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))
            if "NO_ACTIVE_DEVICE" in str(e):
                return await utils.answer(message, self.strings['no_song_playing'])
            return await utils.answer(message, self.strings['unexpected_error'].format(str(e)))

    @loader.command()
    async def stoplyrics(self, message):
        """Остановить обновление текста в реальном времени"""
        if hasattr(self, '_realtime_lyrics_data') and self._realtime_lyrics_data.get('active'):
            self._realtime_lyrics_data['active'] = False
            await utils.answer(message, self.strings["realtime_stopped"])
        else:
            await utils.answer(message, self.strings["no_realtime_active"])

    @loader.command()
    async def playnow(self, message):
        """Live-отображение текущего трека с текстом в реальном времени"""
        if not self.config['auth_token']:
            return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))

        try:
            sp = spotipy.Spotify(auth=self.config['auth_token'])
            current_playback = sp.current_playback()

            if not current_playback or not current_playback.get('item'):
                return await utils.answer(message, self.strings['no_song_playing'])

            await utils.answer(message, self.strings['track_loading'])

            track = current_playback['item']
            track_name = track.get('name', 'Unknown Track')
            artist_name = track['artists'][0].get('name', 'Unknown Artist')
            track_url = track['external_urls']['spotify']
            duration_ms = track.get('duration_ms', 0)
            track_id = track.get('id', '')

            
            track_info = {
                'track_name': track_name,
                'artist_name': artist_name,
                'album_art': track['album']['images'][0]['url'],
                'track_id': track_id
            }

            card_path = await self._create_song_card_no_time(track_info)
            
            
            lyrics_data = await self._get_synced_lyrics_data(artist_name, track_name, duration_ms)
            
            if lyrics_data:
                initial_caption = "🎵 Ожидание синхронизации..."
            else:
                initial_caption = f"❌ <i>Синхронизированный текст для трека не найден</i>\n\n<a href='{track_url}'>{artist_name} — {track_name}</a>"

            if card_path:
                
                sent_message = await self._client.send_file(
                    message.chat_id,
                    card_path,
                    caption=initial_caption,
                    parse_mode='html',
                    reply_to=message.reply_to_msg_id if message.is_reply else getattr(message, "top_id", None)
                )
                
                
                try:
                    os.remove(card_path)
                except:
                    pass
            else:
                
                sent_message = await utils.answer(message, initial_caption)

            
            if hasattr(self, '_playnow_data') and self._playnow_data.get('active'):
                self._playnow_data['active'] = False

            
            self._playnow_data = {
                'message_id': sent_message.id,
                'chat_id': message.chat_id,
                'lyrics_data': lyrics_data,
                'current_track_id': track_id,
                'last_line_index': -1,
                'active': True
            }
            
            await message.delete()
            
            
            asyncio.create_task(self._playnow_loop())

        except spotipy.oauth2.SpotifyOauthError as e:
            return await utils.answer(message, self.strings['auth_error'].format(str(e)))
        except spotipy.exceptions.SpotifyException as e:
            if "The access token expired" in str(e):
                return await utils.answer(message, self.strings['no_auth_token'].format(self.get_prefix()))
            if "NO_ACTIVE_DEVICE" in str(e):
                return await utils.answer(message, self.strings['no_song_playing'])
            return await utils.answer(message, self.strings['unexpected_error'].format(str(e)))

    @loader.command()
    async def stopplaynow(self, message):
        """Остановить live-отображение трека"""
        if hasattr(self, '_playnow_data') and self._playnow_data.get('active'):
            self._playnow_data['active'] = False
            await utils.answer(message, "✅ <b>Live-отображение трека остановлено</b>")
        else:
            await utils.answer(message, "❌ <b>Сеанс live-отображения не активен</b>")

    @loader.loop(interval=60*40, autostart=True)
    async def loop_token(self):
        """Автоматическое обновление токена"""
        if not self.config['auth_token'] or not self.config['refresh_token']:
            return

        try:
            sp_oauth = spotipy.oauth2.SpotifyOAuth(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret'],
                redirect_uri="https://sp.fajox.one",
                scope=self.config['scopes']
            )

            token_info = sp_oauth.refresh_access_token(self.config['refresh_token'])
            self.config['auth_token'] = token_info['access_token']
            if 'refresh_token' in token_info:
                self.config['refresh_token'] = token_info['refresh_token']
        except Exception as e:
            logger.debug(f"Token refresh failed: {str(e)}")