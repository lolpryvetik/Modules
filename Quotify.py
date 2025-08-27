# ©️ LoLpryvet, 2025
# 🌐 https://github.com/lolpryvetik/Modules/blob/main/Quotify.py
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

import io
import os
import random
import requests
import uuid
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from .. import loader, utils


@loader.tds
class QuotifyMod(loader.Module):
    strings = {
        "name": "Quotify",
        "no_reply": "🚫 <b>Reply to a message to quote it!</b>",
        "processing": "🎨 <b>Creating quote...</b>",
        "error": "❌ <b>Error creating quote</b>",
        "downloading_font": "⬇️ <b>Downloading font...</b>",
        "font_downloaded": "✅ <b>Font downloaded successfully</b>",
        "font_error": "❌ <b>Error downloading font</b>",
        "cfg_font": "Font selection",
        "cfg_custom_font_url": "Custom font URL (.ttf)",
        "cfg_show_reply": "Show reply info in quote",
        "_cfg_cst_font_url": "Direct link to .ttf font file",
        "_cfg_show_reply": "Show '(in reply to...)' text in quotes",
    }
    
    strings_ru = {
        "no_reply": "🚫 <b>Ответьте на сообщение для создания цитаты!</b>",
        "processing": "🎨 <b>Создаю цитату...</b>",
        "error": "❌ <b>Ошибка создания цитаты</b>",
        "downloading_font": "⬇️ <b>Загружаю шрифт...</b>",
        "font_downloaded": "✅ <b>Шрифт успешно загружен</b>",
        "font_error": "❌ <b>Ошибка загрузки шрифта</b>",
        "cfg_font": "Выбор шрифта",
        "cfg_custom_font_url": "Ссылка на кастомный шрифт (.ttf)",
        "cfg_show_reply": "Показывать информацию об ответе в цитате",
        "_cfg_cst_font_url": "Прямая ссылка на файл .ttf шрифта",
        "_cfg_show_reply": "Показывать текст '(в ответ на...)' в цитатах",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "font",
                0,
                lambda: self.strings("cfg_font"),
                validator=loader.validators.Choice([0, 1, 2, 3])
            ),
            loader.ConfigValue(
                "custom_font_url",
                "",
                lambda: self.strings("cfg_custom_font_url"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "show_reply",
                False,
                lambda: self.strings("cfg_show_reply"),
                validator=loader.validators.Boolean(),
            ),
        )
        self.fonts = [
            {
                "name": "Hack",
                "url": "https://github.com/source-foundry/Hack/raw/refs/heads/master/build/ttf/Hack-Bold.ttf"
            },
            {
                "name": "Zpix", 
                "url": "https://github.com/Ar4ikTrirtyFour/windose20/raw/refs/heads/main/fonts/zpix.ttf"
            },
            {
                "name": "Times New Roman",
                "url": "https://github.com/misuchiru03/font-times-new-roman/raw/refs/heads/master/Times%20New%20Roman.ttf"
            },
            {
                "name": "Custom Font",
                "url": None
            }
        ]
        self._font_cache = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        
        for i, font in enumerate(self.fonts[:-1]):
            if not self._font_exists(i):
                await self._download_font(i)

    def _get_font_path(self, font_index):
        if font_index == 3:
            return os.path.join(utils.get_base_dir(), "custom_font.ttf")
        else:
            font_name = self.fonts[font_index]["name"].replace(" ", "_")
            return os.path.join(utils.get_base_dir(), f"{font_name}.ttf")

    def _font_exists(self, font_index):
        return os.path.exists(self._get_font_path(font_index))

    async def _download_font(self, font_index):
        if font_index == 3:
            url = self.config["custom_font_url"]
            if not url:
                return False
        else:
            url = self.fonts[font_index]["url"]
        
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            font_path = self._get_font_path(font_index)
            os.makedirs(os.path.dirname(font_path), exist_ok=True)
            
            with open(font_path, 'wb') as f:
                f.write(response.content)
            
            return True
        except Exception:
            return False

    def _get_user_info(self, user):
        if not user:
            return "Unknown User"
        
        name_parts = []
        if hasattr(user, 'first_name') and user.first_name:
            name_parts.append(user.first_name)
        if hasattr(user, 'last_name') and user.last_name:
            name_parts.append(user.last_name)
        
        if name_parts:
            return " ".join(name_parts)
        elif hasattr(user, 'username') and user.username:
            return f"@{user.username}"
        else:
            return "Unknown User"

    def _get_chat_info(self, chat):
        if not chat:
            return "Unknown Chat"
        return getattr(chat, 'title', 'Unknown Chat')

    async def _get_profile_photo(self, entity):
        try:
            photo = await self.client.download_profile_photo(
                entity, 
                file=io.BytesIO()
            )
            if photo:
                photo.seek(0)
                return photo
        except Exception:
            pass
        return None

    def _wrap_text(self, draw, text, font, max_width):
        lines = []
        paragraphs = text.split('\n')
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                lines.append("")
                continue
                
            words = paragraph.split()
            current_line = []
            
            for word in words:
                test_line = current_line + [word]
                test_text = " ".join(test_line)
                
                try:
                    bbox = draw.textbbox((0, 0), test_text, font=font)
                    width = bbox[2] - bbox[0]
                except AttributeError:
                    width = draw.textsize(test_text, font=font)[0]
                
                if width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
            
            if current_line:
                lines.append(" ".join(current_line))
        
        return "\n".join(lines)

    async def _create_quote_image(self, message, author_name, profile_photo=None):
        canvas_width = 900
        min_canvas_height = 400
        img_width = 300
        padding = 30
        
        font_index = self.config["font"]
        
        if not self._font_exists(font_index):
            if not await self._download_font(font_index):
                font_index = 0
                if not self._font_exists(font_index):
                    await self._download_font(font_index)
        
        font_path = self._get_font_path(font_index)
        try:
            quote_font = ImageFont.truetype(font_path, 36)
            author_font = ImageFont.truetype(font_path, 28)
        except Exception:
            quote_font = ImageFont.load_default()
            author_font = ImageFont.load_default()
        
        dummy_img = Image.new("RGB", (canvas_width, min_canvas_height), (0, 0, 0))
        dummy_draw = ImageDraw.Draw(dummy_img)
        
        max_text_width = canvas_width - img_width - padding * 3
        wrapped_quote = self._wrap_text(dummy_draw, message, quote_font, max_text_width)
        author_text = f"— {author_name}"
        
        try:
            quote_bbox = dummy_draw.multiline_textbbox((0, 0), wrapped_quote, font=quote_font)
            author_bbox = dummy_draw.textbbox((0, 0), author_text, font=author_font)
            quote_height = quote_bbox[3] - quote_bbox[1]
            author_height = author_bbox[3] - author_bbox[1]
        except AttributeError:
            quote_height = dummy_draw.multiline_textsize(wrapped_quote, font=quote_font)[1]
            author_height = dummy_draw.textsize(author_text, font=author_font)[1]
        
        total_text_height = quote_height + author_height + 15
        canvas_height = max(min_canvas_height, total_text_height + padding * 2)
        
        if profile_photo:
            try:
                bg_img = Image.open(profile_photo).convert("RGBA")
                scale = max(canvas_width / bg_img.width, canvas_height / bg_img.height)
                new_size = (int(bg_img.width * scale), int(bg_img.height * scale))
                bg_img = bg_img.resize(new_size, Image.Resampling.LANCZOS)
                
                left = (bg_img.width - canvas_width) // 2
                top = (bg_img.height - canvas_height) // 2
                bg_img = bg_img.crop((left, top, left + canvas_width, top + canvas_height))
                
                bg_img = bg_img.filter(ImageFilter.GaussianBlur(24))
                overlay = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 160))
                bg_img = Image.alpha_composite(bg_img, overlay)
                canvas = bg_img.convert("RGB")
            except Exception:
                canvas = Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0))
        else:
            canvas = Image.new("RGB", (canvas_width, canvas_height), (0, 0, 0))
        
        draw = ImageDraw.Draw(canvas)
        
        if profile_photo:
            try:
                profile_img = Image.open(profile_photo).convert("RGBA")
                profile_img = profile_img.resize((img_width, img_width), Image.Resampling.LANCZOS)
                
                mask = Image.new("L", (img_width, img_width), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, img_width, img_width), fill=255)
                profile_img.putalpha(mask)
            except Exception:
                profile_photo = None
        
        if not profile_photo:
            profile_img = Image.new("RGBA", (img_width, img_width), (0, 0, 0, 0))
            profile_draw = ImageDraw.Draw(profile_img)
            
            color = tuple(random.randint(100, 255) for _ in range(3))
            profile_draw.ellipse((0, 0, img_width, img_width), fill=color)
            
            letter = author_name.strip()[0].upper() if author_name.strip() else "?"
            try:
                letter_font = ImageFont.truetype(font_path, int(img_width * 0.4))
            except Exception:
                letter_font = ImageFont.load_default()
            
            try:
                letter_bbox = profile_draw.textbbox((0, 0), letter, font=letter_font)
                letter_width = letter_bbox[2] - letter_bbox[0]
                letter_height = letter_bbox[3] - letter_bbox[1]
            except AttributeError:
                letter_width, letter_height = profile_draw.textsize(letter, font=letter_font)
            
            letter_x = (img_width - letter_width) // 2
            letter_y = (img_width - letter_height) // 2
            profile_draw.text((letter_x, letter_y), letter, font=letter_font, fill=(255, 255, 255))
        
        img_y = (canvas_height - img_width) // 2
        canvas.paste(profile_img, (padding, img_y), profile_img)
        
        text_x = padding + img_width + padding
        text_y = (canvas_height - total_text_height) // 2
        
        draw.multiline_text((text_x, text_y), wrapped_quote, font=quote_font, fill=(255, 255, 255))
        draw.text((text_x, text_y + quote_height + 10), author_text, font=author_font, fill=(180, 180, 180))
        
        output = io.BytesIO()
        canvas.save(output, format='JPEG', quality=95)
        output.seek(0)
        output.name = "quote.jpg"
        
        return output

    @loader.command(
        ru_doc="Создать цитату из отвеченного сообщения"
    )
    async def qcmd(self, message):
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, self.strings("no_reply"))
            return
        
        await utils.answer(message, self.strings("processing"))
        
        try:
            quote_text = reply.raw_text or "[Media]"
            
            if reply.forward:
                if reply.forward.from_name:
                    author_name = reply.forward.from_name
                    author_entity = None
                elif reply.forward.from_id:
                    author_entity = await self.client.get_entity(reply.forward.from_id)
                    author_name = self._get_user_info(author_entity)
                else:
                    author_name = "Forwarded"
                    author_entity = None
            else:
                author_entity = reply.sender
                if reply.sender_id < 0:
                    chat = await self.client.get_entity(reply.peer_id)
                    author_name = self._get_chat_info(chat)
                    author_entity = chat
                else:
                    author_name = self._get_user_info(author_entity)
            
            profile_photo = None
            if author_entity:
                profile_photo = await self._get_profile_photo(author_entity)
            
            if self.config["show_reply"] and reply.reply_to:
                try:
                    replied_to = await reply.get_reply_message()
                    if replied_to:
                        replied_author = self._get_user_info(replied_to.sender)
                        quote_text = f"[in reply to {replied_author}]\n{quote_text}"
                except Exception:
                    pass
            
            quote_image = await self._create_quote_image(quote_text, author_name, profile_photo)
            
            await self.client.send_file(
                message.peer_id,
                quote_image,
                force_document=False,
                supports_streaming=True
            )
            
            await message.delete()
            
        except Exception as e:
            await utils.answer(message, f"{self.strings('error')}: {str(e)}")

    @loader.command(
        ru_doc="Настройки модуля цитат"
    )
    async def qconfigcmd(self, message):
        args = utils.get_args_raw(message)
        
        if not args:
            config_text = (
                f"<b>📄 Quotify Configuration</b>\n\n"
                f"<b>Font:</b> {self.fonts[self.config['font']]['name']}\n"
                f"<b>Custom Font URL:</b> {self.config['custom_font_url'] or 'Not set'}\n"
                f"<b>Show Reply:</b> {self.config['show_reply']}\n\n"
                f"<b>Usage:</b>\n"
                f"<code>.qconfig font [0-3]</code> - Set font (0: Hack, 1: Zpix, 2: Times, 3: Custom)\n"
                f"<code>.qconfig custom_url [URL]</code> - Set custom font URL\n"
                f"<code>.qconfig show_reply [true/false]</code> - Toggle reply info\n"
            )
            await utils.answer(message, config_text)
            return
        
        parts = args.split(None, 1)
        param = parts[0].lower()
        value = parts[1] if len(parts) > 1 else None
        
        if param == "font":
            if value and value.isdigit():
                font_index = int(value)
                if 0 <= font_index <= 3:
                    self.config["font"] = font_index
                    await utils.answer(message, f"✅ Font set to: {self.fonts[font_index]['name']}")
                else:
                    await utils.answer(message, "❌ Font index must be 0-3")
            else:
                await utils.answer(message, "❌ Please provide font index (0-3)")
        
        elif param == "custom_url":
            if value:
                self.config["custom_font_url"] = value
                await utils.answer(message, "✅ Custom font URL updated")
            else:
                await utils.answer(message, "❌ Please provide font URL")
        
        elif param == "show_reply":
            if value:
                if value.lower() in ["true", "1", "yes", "on"]:
                    self.config["show_reply"] = True
                    await utils.answer(message, "✅ Reply info enabled")
                elif value.lower() in ["false", "0", "no", "off"]:
                    self.config["show_reply"] = False
                    await utils.answer(message, "✅ Reply info disabled")
                else:
                    await utils.answer(message, "❌ Use true/false")
            else:
                await utils.answer(message, "❌ Please specify true/false")
        
        else:
            await utils.answer(message, "❌ Unknown parameter. Use: font, custom_url, show_reply")
