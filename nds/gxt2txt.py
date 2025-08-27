import os
import glob
import struct
import requests
from typing import List, Tuple, Dict
import re
import msvcrt

# Global settings
current_file = ""
use_mapping = True
add_translation_line = False
show_warn_message = True
add_translated_text = False
translating_api_key = ""
translating_lang = ""
mapping = []
tags = []
repair_tags = []

# Symbol mapping from the provided table
symbol_map = {
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E', 0x46: 'F', 0x47: 'G',
    0x48: 'H', 0x49: 'I', 0x4A: 'J', 0x4B: 'K', 0x4C: 'L', 0x4D: 'M', 0x4E: 'N',
    0x4F: 'O', 0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T', 0x55: 'U',
    0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y', 0x5A: 'Z', 0x5C: 'a', 0x5D: 'b',
    0x5E: 'c', 0x5F: 'd', 0x60: 'e', 0x61: 'f', 0x62: 'g', 0x63: 'h', 0x64: 'i',
    0x65: 'j', 0x66: 'k', 0x67: 'l', 0x68: 'm', 0x69: 'n', 0x6A: 'o', 0x6B: 'p',
    0x6C: 'q', 0x6D: 'r', 0x6E: 's', 0x6F: 't', 0x70: 'u', 0x71: 'v', 0x72: 'w',
    0x73: 'x', 0x74: 'y', 0x75: 'z'
}

def set_current_file(filename: str):
    global current_file
    current_file = filename

def show_message(message: str):
    print(f"Message for {current_file}: {message}")
    return False

def read_whole_file(file):
    output = ""
    while True:
        char = file.read(1)
        if not char:
            break
        output += char
    return output

def skip_bom(file):
    file.seek(0)
    size = os.path.getsize(file.name)
    if size > 1:
        bom = file.read(2)
        if bom != b'\xFF\xFE':
            file.seek(0)

def read_whole_line(file) -> Tuple[bool, str]:
    if file.tell() >= os.path.getsize(file.name):
        return False, ""
    line = ""
    while True:
        char = file.read(1).decode('utf-16-le', errors='ignore')
        if not char or char in '\r\n':
            break
        line += char
    if char == '\r':
        file.read(1)  # Skip \n
    if line.startswith(';;;'):
        return read_whole_line(file)
    return True, line

def symbol_to_value(s: str) -> int:
    if len(s) > 2 and s.startswith('0x'):
        return int(s[2:], 16)
    return ord(s[0])

def read_settings_files():
    global use_mapping, add_translation_line, show_warn_message, add_translated_text
    global translating_api_key, translating_lang, mapping, tags

    print("Reading settings ...")
    try:
        with open("settings.dat", "r", encoding='utf-16-le') as file:
            skip_bom(file)
            lines = file.readlines()
            i = 0
            if i < len(lines):
                parts = lines[i].strip().split()
                if len(parts) >= 2 and parts[0] == "SHOW_WARN_MESSAGE":
                    show_warn_message = int(parts[1]) == 1
                    print(f"SHOW_WARN_MESSAGE      {int(show_warn_message)}")
                else:
                    print("SHOW_WARN_MESSAGE      UNKNOWN")
                i += 1
            if i < len(lines):
                parts = lines[i].strip().split()
                if len(parts) >= 2 and parts[0] == "USE_MAPPING":
                    use_mapping = int(parts[1]) == 1
                    print(f"USE_MAPPING            {int(use_mapping)}")
                else:
                    print("USE_MAPPING            UNKNOWN")
                i += 1
            if i < len(lines):
                parts = lines[i].strip().split()
                if len(parts) >= 2 and parts[0] == "ADD_TRANSLATION_LINE":
                    add_translation_line = int(parts[1]) == 1
                    print(f"ADD_TRANSLATION_LINE   {int(add_translation_line)}")
                else:
                    print("ADD_TRANSLATION_LINE   UNKNOWN")
                i += 1
            if i < len(lines):
                parts = lines[i].strip().split()
                if len(parts) >= 2 and parts[0] == "ADD_TRANSLATED_TEXT":
                    add_translated_text = int(parts[1]) == 1
                    print(f"ADD_TRANSLATED_TEXT    {int(add_translated_text)}")
                else:
                    print("ADD_TRANSLATED_TEXT    UNKNOWN")
                i += 1
            if i < len(lines):
                parts = lines[i].strip().split(maxsplit=1)
                if len(parts) >= 2 and parts[0] == "TRANSLATION_LANGUAGE":
                    translating_lang = parts[1]
                    print(f"TRANSLATION_LANGUAGE   {translating_lang}")
                else:
                    print("TRANSLATION_LANGUAGE   UNKNOWN")
                    translating_api_key = ""
                i += 1
            if i < len(lines):
                parts = lines[i].strip().split(maxsplit=1)
                if len(parts) >= 2 and parts[0] == "ONLINE_TRANSLATING_KEY":
                    translating_api_key = parts[1]
                    print(f"ONLINE_TRANSLATING_KEY {translating_api_key}")
                else:
                    print("ONLINE_TRANSLATING_KEY UNKNOWN")
                    translating_api_key = ""
            print("Done")
    except FileNotFoundError:
        print('File ("settings.dat") not found')

    print("Reading tags ...")
    try:
        with open("tags.dat", "r", encoding='utf-16-le') as file:
            skip_bom(file)
            tags = []
            for line in file:
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    tags.append({'symbol': symbol_to_value(parts[0]), 'tagname': parts[1]})
            n, m = divmod(len(tags), 3)
            for i in range(n):
                for j in range(3):
                    tag = tags[j + i * 3]
                    print(f"[0x{tag['symbol']:X} > ~{tag['tagname']}~]", end="")
                    print("\n" if j == 2 else " ", end="")
            for i in range(m):
                tag = tags[i + n * 3]
                print(f"[0x{tag['symbol']:X} > ~{tag['tagname']}~]", end="")
                print(" " if i != m - 1 else "\n", end="")
            print("Done\n")
    except FileNotFoundError:
        print('File ("tags.dat") not found')

def get_tag(symbol: int) -> str:
    for tag in tags:
        if tag['symbol'] == symbol:
            return tag['tagname']
    return None

def tag_to_symbol(line_number: int, input_str: str, input_pos: int, output: List[str]) -> int:
    tag = ""
    tag_closed = False
    for i in range(input_pos + 1, len(input_str)):
        if input_str[i] == '~':
            tag_closed = True
            break
        tag += input_str[i]
    if tag_closed:
        if tag == 'n':
            output.append('\n')
            return 1
        elif len(tag) == 5 and tag[0] == '#':
            try:
                result = int(tag[1:], 16)
                output.append(chr(result))
                return 5
            except ValueError:
                pass
        else:
            for tag_info in tags:
                if tag_info['tagname'].lower() == tag.lower():
                    output.append(chr(tag_info['symbol']))
                    return len(tag_info['tagname'])
        if len(tag) > 16:
            warning = f"\n   warning (line {line_number}): possibly a wrong tag ('~{tag[:16]}...')"
        else:
            warning = f"\n   warning (line {line_number}): possibly a wrong tag ('~{tag}')"
        print(warning)
        if show_warn_message:
            show_message(warning[4:])
        return 0
    return 0

def replace_text_tags_for_translation(s: str) -> str:
    global repair_tags
    repair_tags = []
    output = []
    s_idx = 0
    while s_idx < len(s):
        if s[s_idx] == '~':
            tag = ""
            s_idx += 1
            while s_idx < len(s) and s[s_idx] != '~':
                tag += s[s_idx]
                s_idx += 1
            if s_idx < len(s):
                s_idx += 1
                if tag == 'n':
                    output.append('\n')
                elif len(tag) == 5 and tag[0] == '#':
                    try:
                        value = int(tag[1:], 16)
                        output.append(chr(value))
                    except ValueError:
                        output.append('~' + tag + '~')
                else:
                    found = False
                    for tag_info in tags:
                        if tag_info['tagname'].lower() == tag.lower():
                            newtag = f"[{len(repair_tags)}]"
                            output.append(newtag)
                            oldtag = f"~{tag}~"
                            repair_tags.append({'what': newtag, 'to': oldtag})
                            found = True
                            break
                    if not found:
                        output.append('~' + tag + '~')
        else:
            output.append(s[s_idx])
            s_idx += 1
    return ''.join(output)

def repair_text_tags_after_translation(s: str) -> str:
    for repair in repair_tags:
        s = s.replace(repair['what'], repair['to'])
    return s

def translate_plain_text(text: str) -> str:
    if not translating_api_key:
        return text
    url = f"https://translate.yandex.net/api/v1.5/tr/translate?key={translating_api_key}&text={text}&format=plain"
    if translating_lang:
        url += f"&lang={translating_lang}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            content = response.text
            start = content.find("<text>") + 6
            end = content.find("</text>")
            if start != -1 and end != -1 and end > start:
                return content[start:end]
    except Exception as e:
        print(f"Translation failed: {e}")
    return text

def get_mapped_symbol(symbol: int) -> int:
    if use_mapping and symbol in symbol_map:
        return ord(symbol_map[symbol])
    return symbol

def unmap_symbol(symbol: int) -> int:
    if use_mapping:
        for k, v in symbol_map.items():
            if ord(v) == symbol:
                return k
    return symbol

class CGXTFile:
    def __init__(self, filepath: str = None):
        self.loaded = False
        self.has_warnings = False
        self.strings: List[str] = []
        if filepath:
            self.read(filepath)

    def read(self, filepath: str) -> bool:
        self.strings = []
        self.loaded = False
        self.has_warnings = False
        try:
            with open(filepath, "rb") as file:
                file.seek(0, os.SEEK_END)
                size = file.tell()
                if size <= 7:
                    if show_warn_message:
                        show_message(f'file "{filepath}" is not a valid gxt file')
                    return False
                file.seek(0)
                header = file.read(8)
                signature, num_strings = struct.unpack("<6sH", header)
                if signature != b"DS_GXT":
                    if show_warn_message:
                        show_message(f'file "{filepath}" is not a valid gxt file')
                    return False
                if num_strings > 0:
                    self.strings = []
                    for _ in range(num_strings):
                        str_length = struct.unpack("<H", file.read(2))[0]
                        string_data = file.read(str_length * 2).decode('utf-16-le')
                        self.strings.append(string_data)
                    self.loaded = True
                else:
                    if show_warn_message:
                        show_message(f'file "{filepath}" is not a valid gxt file')
        except Exception as e:
            if show_warn_message:
                show_message(f'failed to open file "{filepath}"')
        if not self.loaded and self.strings:
            self.strings = []
        return self.loaded

    def read_from_text_file(self, filepath: str) -> bool:
        self.strings = []
        self.loaded = False
        self.has_warnings = False
        try:
            with open(filepath, "r", encoding='utf-16-le') as file:
                skip_bom(file)
                success, line = read_whole_line(file)
                if not success or line != "GXT":
                    if show_warn_message:
                        show_message(f'file "{filepath}" is not a valid gxt file')
                    return False
                while True:
                    success, line = read_whole_line(file)
                    if not success:
                        break
                    current_string = []
                    for c_idx, char in enumerate(line, 1):
                        if char == '~':
                            tag_size = tag_to_symbol(len(self.strings) + 1, line, c_idx - 1, current_string)
                            if tag_size != 0:
                                c_idx += tag_size + 1
                            else:
                                current_string.append(chr(unmap_symbol(ord(char))))
                                self.has_warnings = True
                        else:
                            current_string.append(chr(unmap_symbol(ord(char))))
                    current_string = ''.join(current_string)
                    if not current_string:
                        print(f"\n   warning (line {len(self.strings) + 1}): line is empty")
                        if show_warn_message:
                            show_message(f"warning (line {len(self.strings) + 1}): line is empty")
                        self.has_warnings = True
                    self.strings.append(current_string)
                self.loaded = True
        except Exception as e:
            if show_warn_message:
                show_message(f'failed to open file "{filepath}"')
        if not self.loaded and self.strings:
            self.strings = []
        return self.loaded

    def write(self, output_filepath: str):
        with open(output_filepath, "wb") as file:
            file.write(b"DS_GXT")
            file.write(struct.pack("<H", len(self.strings)))
            for i, s in enumerate(self.strings):
                file.write(struct.pack("<H", len(s) + (1 if i == len(self.strings) - 1 else 0)))
                file.write(s.encode('utf-16-le'))
            file.write(struct.pack("<H", 0))

    def write_to_text_file(self, output_filepath: str):
        with open(output_filepath, "wb") as file:
            file.write(b"\xFF\xFE")
            with open(output_filepath, "a", encoding='utf-16-le') as file:
                file.write("GXT")
                if add_translated_text:
                    file.write(" | Переведено «Яндекс.Переводчиком»")
                    if translating_lang:
                        file.write(f" ({translating_lang})")
                for i, s in enumerate(self.strings):
                    if i == 0:
                        file.write("\r\n")
                    formatted_str = ""
                    for c in s:
                        c_val = ord(c)
                        if c_val > 0xFEEF:
                            tag = get_tag(c_val)
                            if tag:
                                formatted_str += f"~{tag}~"
                            else:
                                formatted_str += f"~#{c_val:X}~"
                        elif c_val == 0xA:
                            formatted_str += "~n~"
                        else:
                            formatted_str += chr(get_mapped_symbol(c_val))
                    if add_translation_line:
                        file.write(";;;")
                    file.write(formatted_str)
                    if add_translation_line and add_translated_text:
                        file.write("\r\n")
                        translated = translate_plain_text(replace_text_tags_for_translation(formatted_str))
                        translated = repair_text_tags_after_translation(translated)
                        file.write(translated)
                    if i != len(self.strings) - 1:
                        file.write("\r\n")

class CBinFile:
    def __init__(self, filepath: str = None):
        self.loaded = False
        self.header = {'numSymbolsInFont': 0, 'fontHeight': 10}
        self.symbols_info = []
        if filepath:
            self.read(filepath)

    def read(self, filepath: str) -> bool:
        try:
            with open(filepath, "rb") as file:
                file.seek(0, os.SEEK_END)
                size = file.tell()
                if size < 4:
                    self.loaded = False
                    return False
                file.seek(0)
                self.header['numSymbolsInFont'], self.header['fontHeight'] = struct.unpack("<HH", file.read(4))
                self.symbols_info = []
                for _ in range(self.header['numSymbolsInFont']):
                    width, unknown1, unknown2 = struct.unpack("<HHH", file.read(6))
                    self.symbols_info.append({'width': width, 'unknown1': unknown1, 'unknown2': unknown2})
                self.loaded = True
                return True
        except Exception:
            self.loaded = False
            return False

    def read_from_text_file(self, filepath: str) -> bool:
        try:
            with open(filepath, "r", encoding='utf-16-le') as file:
                skip_bom(file)
                lines = file.readlines()
                i = 0
                if i < len(lines) and lines[i].strip().startswith("BIN"):
                    i += 1
                    if i < len(lines):
                        parts = lines[i].strip().split()
                        if len(parts) >= 2:
                            self.header['fontHeight'] = int(parts[1])
                            i += 1
                        else:
                            return False
                    if i < len(lines):
                        parts = lines[i].strip().split()
                        if len(parts) >= 2:
                            self.header['numSymbolsInFont'] = int(parts[1])
                            self.symbols_info = []
                            i += 1
                        else:
                            return False
                    for _ in range(self.header['numSymbolsInFont']):
                        if i >= len(lines):
                            self.header['numSymbolsInFont'] = 0
                            self.symbols_info = []
                            return False
                        parts = lines[i].strip().split()
                        if len(parts) >= 3:
                            self.symbols_info.append({
                                'width': int(parts[0]),
                                'unknown1': int(parts[1]),
                                'unknown2': int(parts[2])
                            })
                            i += 1
                        else:
                            self.header['numSymbolsInFont'] = 0
                            self.symbols_info = []
                            return False
                    return True
                return False
        except Exception:
            self.header['numSymbolsInFont'] = 0
            self.symbols_info = []
            return False

    def write(self, output_filepath: str):
        with open(output_filepath, "wb") as file:
            file.write(struct.pack("<HH", self.header['numSymbolsInFont'], self.header['fontHeight']))
            for symbol in self.symbols_info:
                file.write(struct.pack("<HHH", symbol['width'], symbol['unknown1'], symbol['unknown2']))

    def write_to_text_file(self, output_filepath: str):
        with open(output_filepath, "wb") as file:
            file.write(b"\xFF\xFE")
            with open(output_filepath, "a", encoding='utf-16-le') as file:
                file.write(f"BIN\nFONT_HEIGHT  {self.header['fontHeight']}\nFONT_SYMBOLS {self.header['numSymbolsInFont']}\n;width x   y\n")
                for i, symbol in enumerate(self.symbols_info):
                    char = chr(i + 32)
                    file.write(f"   {symbol['width']:<3} {symbol['unknown1']:<3} {symbol['unknown2']:<3}    ;  '{char}'  (0x{i + 32:X})")
                    if i != len(self.symbols_info) - 1:
                        file.write("\r\n")

def main():
    os.system("title GTA Chinatown Wars GXT2TXT Converter")
    print("GTA Chinatown Wars GXT2TXT Converter\n    by DK22\n")
    read_settings_files()
    for filepath in glob.glob("*.gxt"):
        set_current_file(filepath)
        output_filepath = os.path.splitext(filepath)[0] + ".txt"
        print(f"converting {filepath} ... ", end="")
        gxt_file = CGXTFile()
        if gxt_file.read(filepath):
            gxt_file.write_to_text_file(output_filepath)
            if gxt_file.has_warnings:
                print()
            print(f"done ({len(gxt_file.strings)} strings)")
        else:
            print("failed")
    print("\nConversion done. Press any key to exit.")
    msvcrt.getch()

if __name__ == "__main__":
    main()