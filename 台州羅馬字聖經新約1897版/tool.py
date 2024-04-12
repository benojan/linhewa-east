import pathlib
import re
from collections import Counter

# RE_HAN = r"[\u2E80-\u2FFF\u3007\u31C0-\u31EF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF"\
#          r"\U00020000-\U0002A6DF\U0002A700-\U0002EE5F\U0002F800-\U0002FA1F\U00030000-\U000323AF]"
RE_HAN = r"\{.+?\}|[\u4E00-\u9FA5❓□㾎𧮙䫲𤖼𠡒𣥼䂸㔶䥛䀹㬹㧒]"

class LineInfo:

    BOOK = 1            # '# '
    CHAPTER = 2         # '## '
    VERSE = 3           # '·'
    PREV = 4            # '**_'
    TRANS_PREV = 5      # '> **_'
    TRANS = 6           # '> '
    FOOTNOTE_SIGN = 7   # '------'
    FOOTNOTE = 8        # '[^'
    OTHER = 9           

    def __init__(self, line: str) -> None:
        """获取一行的类型等信息，请确保 `line` 不以换行符结尾。"""
        self.suffix = ""
        if line.startswith("# "):
            self.type = LineInfo.BOOK
            self.prefix = "# "
            self.content = line[2:]
            self.offset = 2
        elif line.startswith("## "):
            self.type = LineInfo.CHAPTER
            self.prefix = "## "
            self.content = line[3:]
            self.offset = 3
        elif line.startswith("·"):
            self.type = LineInfo.VERSE
            self.prefix = "·"
            self.content = line[1:]
            self.offset = 1
        elif line.startswith("**_"):
            self.type = LineInfo.PREV
            self.prefix = "**_"
            self.content = line[3:].removesuffix("_**")
            self.offset = 3
            self.suffix = "_**"
        elif line.startswith("> **_"):
            self.type = LineInfo.TRANS_PREV
            self.prefix = "> **_"
            self.content = line[5:].removesuffix("_**")
            self.offset = 5
            self.suffix = "_**"
        elif line.startswith("> "):
            self.type = LineInfo.TRANS
            self.prefix = "> "
            self.content = line[2:]
            self.offset = 2
        elif line.startswith("------"):
            self.type = LineInfo.FOOTNOTE_SIGN
            self.prefix = ""
            self.content = "------"
            self.offset = 0
        elif line.startswith("[^") and line.find("]: ") != -1:
            self.type = LineInfo.FOOTNOTE
            r = line.find("]: ")
            self.prefix = line[0:r+3]
            self.content = line[r+3:]
            self.offset = r + 3
        else:
            self.type = LineInfo.OTHER
            self.prefix = ""
            self.content = line
            self.suffix = ""
            self.offset = 0

    def get_trans_prefix_and_suffix(self) -> tuple:
        """获取对应译文的标头和标尾"""
        if self.type == LineInfo.BOOK \
            or self.type == LineInfo.CHAPTER\
                or self.type == LineInfo.VERSE:
            return ("> ", "")
        elif self.type == LineInfo.PREV:
            return ("> **_", "_**")
        else:
            return (self.prefix, self.suffix)


class Books(list[dict]):
    """books 列表。其格式如下:
    ```
    [book{}, book{}...],
    ```
    ---
    其中 `book{}` 格式如下：
    ```
    { 'book_name': {'line_no': 行号, 'lat': 原文, 'han': 译文},
      'chapters':  [chapter{}, chapter{}...],
      'footnotes': ['xx', 'xx'...] }
    ```
    ---
     其中的 `chapter{}` 格式如下：
    ```
    { 'line_no': 行号,
      'title':   标题(如'Mt. 4.'),
      'verses':  [verse{}, verse{}...] }
    ```
    ---
    其中的 `verse{}` 格式如下：
    ```
    { 'line_no': 行号, 'lat': 原文, 'han': 译文 }
    ```
    """

    # 目前只能查 分词。无法查分字或分词组成的词。
    def find_relative_ci(self, lat_ci: str, han_ci: str) -> None:
        """
        在 books 中查找 相互对应 的 lat_ci 和 han_ci，输出找到的内容。
        """
        # 检验输入
        lat_ci = lat_ci.lower()
        (q_list_lat, q_list_han) = Books._verse_fenzi({'lat':lat_ci, 'han':han_ci})
        if len(q_list_lat) == 0 or len(q_list_han) == 0:
            print("🔴 请输入正确的内容！")
            return 
        if len(q_list_lat) != len(q_list_han):
            print(f"🔴 输入的分字数量不一致！"
                  f"lat: {len(q_list_lat)}, han: {len(q_list_han)}")
            return
        # 查找
        for book in self:
            for chap_index,chapter in enumerate(book['chapters']):
                for verse_no,verse in enumerate(chapter['verses']):
                    details = Books._verse_fenci_with_details(verse)
                    # [{'lat':xx, 'lat_span':xx, 'han':xx, 'han_span':xxx}, ...]
                    select = []
                    for ci_info in details:
                        if ci_info['lat'] == lat_ci and ci_info['han'] == han_ci:
                            select.append(ci_info)
                    show_lat = verse['lat']
                    show_han = verse['han']
                    if len(select)>0:
                        print(f"🟢 在《{book['book_name']['han']}》, 第 {chap_index+1} 章, 第 {verse_no} 节: (第 {verse['line_no']} 行)")
                    else:
                        continue
                    select.reverse()    # 从右往左替换，这样左边的下标不变
                    for ci_info in select:
                        lat_span = ci_info['lat_span']
                        han_span = ci_info['han_span']
                        show_lat = show_lat[0:lat_span[0]] + "👉🏻" + show_lat[lat_span[0]:lat_span[1]] + "👈🏻" + show_lat[lat_span[1]:]
                        show_han = show_han[0:han_span[0]] + "👉" + show_han[han_span[0]:han_span[1]] + "👈" + show_han[han_span[1]:]
                        print(f"lat: " + show_lat)
                        print(f"han: " + show_han)

    def fenci(self, zi:bool=False) -> Counter|None:
        """对 books 里的 verses 进行分词或分字统计。

        参数: 
            `zi`: 是否分字，默认为分词。
        
        返回: `Counter`。 {(lat, han): count}
        """
        counter = Counter()

        for book in self:
            for chapter in book['chapters']:
                for verse in chapter['verses']:
                    # 先判断原文和译文的字数是否统一
                    (list_lat_zi, list_han_zi) = Books._verse_fenzi(verse)
                    if len(list_han_zi) != len(list_lat_zi):
                        print(f"🔴 {book['book_name']['han']}-第 {verse['line_no']} 行: "
                              "翻译字数与原文不符：")
                        print(f"    lat: {verse['lat']}")
                        print(f"    han: {verse['han']}\n函数中止！请修正！")
                        return None
                    if zi:
                        counter.update(list(zip(list_lat_zi, list_han_zi)))
                    else:
                        (list_lat_ci, list_han_ci) = Books._verse_fenci(verse, list_han_zi)
                        counter.update(list(zip(list_lat_ci, list_han_ci)))
        return counter

    def get_verse(self, book_no:int|str, chapter_no:int, verse_no:int):
        """获取一个小节。no 从 1 开始，但 verse_no 可设为 0 来获取概述小节。"""
        if type(book_no) == str and not book_no.isdigit():
            book_index = book_names.find_index(book_no)
        elif type(book_no) == int or book_no.isdigit():
            book_no = int(book_no)
            book_index = book_no - 1
        else:
            raise TypeError("book_no 参数只支持 整数编号 或 书名。")
        chapter_index = chapter_no - 1
        if book_index<0 or chapter_index<0:
            return None
        verse_index = verse_no  # 0 表示概述小节
        verse = self[book_index]['chapters'][chapter_index]['verses'][verse_index]
        return verse

    def forEach_verse(self, oper):
        """对每一节回调 `oper(verse)` 函数。
        """
        for book in self:
            for chapter in book['chapters']:
                for verse in chapter['verses']:
                    oper(verse)


    # class functions

    _re_note = re.compile(r"\[.+?\]")    # 用于 去除 verse 中的 [...]
    _re_lat_zi = re.compile(r"['a-zA-ZÜüÔôÖöÆæ]+")
    _re_han_zi = re.compile(r"\{.+?\}|[\u4E00-\u9FA5❓□㾎𧮙䫲𤖼𠡒𣥼䂸㔶䥛䀹㬹㧒]")
    _re_lat_ci = re.compile(r"['a-zA-ZÜüÔôÖöÆæ-]+")

    def _verse_fenzi(verse:dict)->tuple[list,list]:
        """对单条 verse 进行分字。
        
        verse 格式：{'lat':xxx, 'han':xxx}
        
        返回 (list_lat_zi, list_han_zi)
        """
        verse_lat = verse['lat'].lower()
        verse_han = verse['han']
        verse_lat = Books._re_note.sub("", verse_lat) # 去掉[...]
        list_lat_zi = Books._re_lat_zi.findall(verse_lat)
        list_han_zi = Books._re_han_zi.findall(verse_han)
        return (list_lat_zi, list_han_zi)

    def _verse_fenci(verse:dict, list_han_zi:list=None)->tuple[list,list]:
        """对单条 verse 进行分词。基于 罗马字文本 的连字符。
        
        verse 格式：{'lat':xxx, 'han':xxx}

        参数 `list_han_zi`: 可选。表示已分好字的汉字列表。加快速度。
        
        返回 (list_lat_zi, list_han_zi)
        """
        verse_lat = verse['lat'].lower()
        verse_lat = Books._re_note.sub("", verse_lat) # 去掉[...]
        list_lat_ci = Books._re_lat_ci.findall(verse_lat)
        if list_han_zi == None:
            verse_han = verse['han']
            list_han_zi = Books._re_han_zi.findall(verse_han)
        list_han_ci = []
        index = 0
        for lat_ci in list_lat_ci:
            zi_count = lat_ci.count('-')+1
            han_ci = "".join(list_han_zi[index:index+zi_count])
            list_han_ci.append(han_ci)
            index += zi_count
        return (list_lat_ci, list_han_ci)

    def _verse_fenci_with_details(verse:dict)->list[dict]:
        """分词并带有下标细节。
        返回 [{'lat':xxx, 'han':xxx, 'lat_span':xxx, 'han_span':xxx}, ...]
        """
        details = []
        lat = verse['lat'].lower()
        han = verse['han']
        # lat = Books._re_note.sub("", lat) # 去掉 [...]
        lat_ci_with_note_matches = Books._re_lat_ci.finditer(lat)
        # 去掉 [...]，因为涉及到下标，不能对原文本进行 sub，所以以这方式
        note_matches = Books._re_note.finditer(lat)
        note_matches = list(note_matches) # 需要多次遍历，加进列表里
        if len(note_matches) == 0:
            lat_ci_matches = lat_ci_with_note_matches
        else:
            lat_ci_matches = []
            for match in lat_ci_with_note_matches:
                need_added = True
                for note in note_matches:   # 需要多次遍历，所以上面加进列表里
                    if match.span()[0] > note.span()[0] and match.span()[1] < note.span()[1]:
                        need_added = False
                        break
                if need_added:
                    lat_ci_matches.append(match)

        han_zi_matches = Books._re_han_zi.finditer(han)
        han_zi_matches = list(han_zi_matches)
        
        list_han_zi = [match.group() for match in han_zi_matches]
        index = 0
        for lat_ci_match in lat_ci_matches:
            ci = {}
            ci['lat'] = lat_ci_match.group()
            ci['lat_span'] = lat_ci_match.span()    
            zi_count = ci['lat'].count("-")+1
            han_ci = list_han_zi[index:index+zi_count]
            span_start = han_zi_matches[index].span()[0]
            span_end = han_zi_matches[index+zi_count-1].span()[1]
            ci['han'] = "".join(han_ci)
            ci['han_span'] = (span_start, span_end)
            details.append(ci)
            index += zi_count

        return details

def validate_origin_punc(origin_path: str):
    """验证原文文本标点符号格式是否正确。
    
    Args:
        file_path: 原文文本路径。
    """
    with open(origin_path, encoding="utf-8") as f:
        no = 0
        for line in f:
            no += 1
            if line == "\n":
                continue
            line = line.strip() # 去除换行符
            line_info = LineInfo(line)
            type = line_info.type
            offset = line_info.offset
            text = line_info.content
            if type != LineInfo.VERSE and type != LineInfo.PREV:
                continue
            # 开始处理
            text = "(" + text + "\n" # 添加头尾方便遍历
            index = 1
            while index < len(text)-1: # 遍历行内字符
                letter = text[index]
                prev = text[index-1]
                next = text[index+1]
                if letter == '[':   # 注解或引用，需持续匹配
                    ref = False
                    if next == "^" and prev == " ":
                        print(f"🟡 行-{no}, 列-{index+offset}: [^...] 注释前不要空格。")
                    elif next != "^" and prev not in " ‘“(":
                        print(f"🟡 行-{no}, 列-{index+offset}: [ 前缺少空格。")
                    if next == "^":
                        ref = True
                    while index < len(text)-1: # 持续匹配
                        index += 1
                        if index == len(text)-1: # 到达末尾
                            if text[index] != "]":
                                print(f"🟡 行-{no}, 列-{index+offset}: 缺少与 [ 匹配的 ]。")
                            break
                        if text[index] == "]": # 未到达末尾
                            if ref: break
                            if text[index+1] not in "\n )’”":
                                print(f"🟡 行-{no}, 列-{index+offset}: ] 后缺少空格。")
                            break
                elif letter in ",.;:!?":
                    if next not in "\n ’”)]_":
                        print(f"🟡 行-{no}, 列-{index+offset}: {letter} 后缺少空格。")
                elif letter == "‘":
                    if prev not in " “[(":
                        print(f"🟡 行-{no}, 列-{index+offset}: ‘ 前缺少空格。")
                elif letter == '“':
                    if prev not in " ‘[(":
                        print(f"🟡 行-{no}, 列-{index+offset}: “ 前缺少空格。")
                elif letter == "’":
                    if next not in "\n ,.:;”)]":
                        print(f"🟡 行-{no}, 列-{index+offset}: ’ 后缺少空格。")
                elif letter == '”':
                    if next not in "\n ,.:;’)]":
                        print(f"🟡 行-{no}, 列-{index+offset}: ” 后缺少空格。")
                elif letter == "—":
                    if prev not in " [(‘“":
                        print(f"🟡 行-{no}, 列-{index+offset}: — 前缺少空格。")
                    if next == '—':
                        print(f"🟡 行-{no}, 列-{index+offset}: — 太长了，删掉一半。")
                        index += 1 # 消耗掉
                    elif next not in "\n ’”)]":
                        print(f"🟡 行-{no}, 列-{index+offset}: — 后缺少空格。")
                index += 1

def generate_trans_file(origin_path: str, trans_path: str=None, fenci:Counter=None):
    """根据原文文本生成翻译文本模板。

    参数：
        `from_path`: 原文文本路径
        `to_path`: 翻译文本路径
        `fenci`: 可选的分词对象
    """
    if origin_path == trans_path:
        print("🔴 警告: 原文路径不能与目标路径相同！")
        return
    if trans_path == None:
        trans_path = "temp.md"
    elif pathlib.Path(trans_path).exists():
        print("🔴 警告: 目标路径已存在，如需重新生成，请先手动删除！\n"
              f"目标路径: {trans_path}")
        return
    with (open(origin_path, "r", encoding="utf-8") as rf,
          open(trans_path, "w", encoding="utf-8") as wf):
        for line in rf:
            wf.write(line)
            line = line.strip()
            line_info = LineInfo(line)
            type = line_info.type
            if type == LineInfo.BOOK or type == LineInfo.VERSE:
                wf.write("\n")
                wf.write(line_info.get_trans_prefix_and_suffix()[0])
                if fenci != None:
                    wf.write(lat2han(line_info.content, fenci))
                wf.write("\n")
            elif type == LineInfo.CHAPTER:
                wf.write("\n")
                wf.write(line_info.get_trans_prefix_and_suffix()[0])
                wf.write(line_info.content)
                wf.write("\n")
            elif type == LineInfo.PREV:
                wf.write("\n")
                (prefix, suffix) = line_info.get_trans_prefix_and_suffix()
                wf.write(prefix)
                if fenci != None:
                    wf.write(lat2han(line_info.content, fenci))
                wf.write(suffix)
                wf.write("\n")
        print(f"已完成，请查看 {trans_path}")

def _load_trans_book(trans_path: str) -> dict:
    """请使用 `load_trans_books()` 。"""
    book = {}
    book['book_name'] = {}
    book['chapters'] = list[dict]()
    book['footnotes'] = list[str]()
    with open(trans_path, 'r', encoding='utf-8') as f:
        line_no = 0
        handle_footnotes = False
        while (line := f.readline()) != '':
            line_no += 1
            line_info = LineInfo(line.strip())
            type = line_info.type

            # 检测为书名行
            if type == LineInfo.BOOK:
                book['book_name']['line_no'] = line_no
                book['book_name']['lat'] = line_info.content
                if f.readline() != '\n':
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 书名行下未空一行，函数中止！")
                    return None
                han_line = f.readline()
                han_line_info = LineInfo(han_line.strip())
                if han_line_info.type != LineInfo.TRANS:
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 书名行未翻译，函数中止！")
                    return None
                line_no += 2
                book['book_name']['han'] = han_line_info.content
                if f.readline() != '\n':
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 书名翻译行下未空一行，函数中止！")
                    return None
                line_no += 1

            # 检测为章标题行
            elif type == LineInfo.CHAPTER:
                book['chapters'].append({})
                book['chapters'][-1]['line_no'] = line_no
                book['chapters'][-1]['title'] = line_info.content
                book['chapters'][-1]['verses'] = list[dict]()
                if f.readline() != '\n':
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 章标题行下未空一行，函数中止！")
                    return None
                han_line = f.readline()
                han_line_info = LineInfo(han_line.strip())
                if han_line_info.type != LineInfo.TRANS:
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 章标题行未有对应的中文版本，函数中止！")
                    return None
                line_no += 2
                if f.readline() != '\n':
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 章标题行下未空一行，函数中止！")
                    return None
                line_no += 1

            # 检测为小节行或概述行
            elif type == LineInfo.VERSE or type == LineInfo.PREV:
                if len(book['chapters']) == 0:
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 该小节之前未创建章，函数中止！")
                    return None
                _verse = {}
                _verse['line_no'] = line_no
                _verse['lat'] = line.strip()    # 保留原格式
                if f.readline() != '\n':
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 小节行下未空一行，函数中止！")
                    return None
                han_line = f.readline()
                han_line_info = LineInfo(han_line.strip())
                if line_info.type == LineInfo.PREV and han_line_info.type != LineInfo.TRANS_PREV:
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 概述行未翻译，函数中止！")
                    return None
                elif line_info.type == LineInfo.VERSE and han_line_info.type != LineInfo.TRANS:
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 小节行未翻译，函数中止！")
                    return None
                line_no += 2
                _verse['han'] = han_line.strip() # 保留原格式
                book['chapters'][-1]['verses'].append(_verse)
                if f.readline() != '\n':
                    print(f"🔴 在 {trans_path} 中:")
                    print(f"    行-{line_no}: 小节或概述翻译行下未空一行，函数中止！")
                    return None
                line_no += 1

            # 检测为空行
            elif line.startswith("\n"):
                pass
            # 检测为脚注行
            elif type == LineInfo.FOOTNOTE_SIGN:
                handle_footnotes = True
            elif handle_footnotes:
                book['footnotes'].append(line.strip())
            # 检测到未知行
            else:
                print(f"🔴 在 {trans_path} 中:")
                print(f"    行-{line_no}: 未知行，函数中止！")
                return None
    return book

def load_trans_books(*trans_paths: str) -> Books|None:
    """加载译文文本，保存为类似 json 数据对象。

    使用方式: 
        `books = load_trans_books(path1, path2, ...)`
    载入失败则返回 `None`。
    ---
    books 的格式如下:
    ```
    [{'book_name': {'line_no': 行号, 'lat': 原文, 'han': 译文},
      'chapters':  [{'line_no': 行号, 
                     'title': 标题(如'Mt. 4.'),
                     'verses': [{'line_no': 行号, 
                                 'lat': 原文, 
                                 'han': 译文}, ...]
                    }, ...],
      'footnotes': ['xx', 'xx', ...]},
     }, ...]
    ```
    """
    books = Books()
    for path in trans_paths:
        book = _load_trans_book(path)
        if book is None:
            return None
        else:
            books.append(book)
    return books

def lat2han(lat:str, fenci:Counter) -> str:
    # 未完善
    result = []
    lat = lat.lower()
    lat = re.sub(r"\[.+?\]", "", lat) # 去除中括号及内容
    items = re.findall("[0-9] |[0-9,.;:‘’“”!?()—]|['a-zA-ZÜüÔôÖöÆæ-]+", lat)
    punc_trans = str.maketrans(",.;:‘’“”!?()", "，。；：‘’“”！？（）")
    re_ci = re.compile("['a-zA-ZÜüÔôÖöÆæ-]+")
    fc_list = fenci.most_common()
    for item in items:
        if re_ci.search(item) != None:  # 为词
            ci = None
            for ((la,ha),_) in fc_list:
                if la == item:
                    ci = ha
                    break
            if not ci:
                ci = item
            result.append(ci)
        elif item[0] in "0123456789":
            result.append(item)
        elif item == '—':
            result.append('——')
        else:
            result.append(item.translate(punc_trans))
    return "".join(result)

def han2lat(han:str, fenzi:Counter) -> str:
    # 未完善
    result = []
    need_space = False
    for item in han:
        if re.match(RE_HAN, item) == None:
            result.append(item)
            need_space = False
            continue
        duoyinzi = []
        if need_space:
            result.append(" ")
        for (z_lat, z_han) in fenzi.keys():
            if item == z_han:
                duoyinzi.append(z_lat)
        if len(duoyinzi) == 0:
            result.append(item)
        elif len(duoyinzi) == 1:
            result.append(duoyinzi[0])
        else:
            result.append("/".join(duoyinzi))
        need_space = True
    return "".join(result)


class book_names:

    def find_index(book_name:str)-> int|None:
        book_name = book_name.strip()
        if book_name in book_names.book_names_zh_simp:
            return book_names.book_names_zh_simp.index(book_name)
        if book_name in book_names.book_names_zh_trad:
            return book_names.book_names_zh_trad.index(book_name)
        book_name = book_name.lower()
        if book_name in book_names.book_names_lat:
            return book_names.book_names_zh_simp.index(book_name)
        book_name = book_name.rstrip('. ').replace("'","")
        if book_name in book_names.book_names_lat_abbr:
            return book_names.book_names_zh_simp.index(book_name)
        return None

    book_names_zh_simp = ['马太传福音书', '马可传福音书', '路加传福音书', '约翰传福音书', '使徒行传', 
                '罗马书信', '哥林多书信 1', '哥林多书信 2', '加拉太书信', '以弗所书信', 
                '腓立比书信', '歌罗西书信', '帖撒罗尼迦书信 1', '帖撒罗尼迦书信 2', '提摩太书信 1', 
                '提摩太书信 2', '提多书信', '腓利门书信', '希伯来书信', '雅各书信', 
                '彼得书信 1', '彼得书信 2', '约翰书信 1', '约翰书信 2', '约翰书信 3', 
                '犹大书信', '默示录']

    book_names_zh_trad = ['馬太傳福音書', '馬可傳福音書', '路加傳福音書', '約翰傳福音書', '使徒行傳', 
                '羅馬書信', '哥林多書信 1', '哥林多書信 2', '加拉太書信', '以弗所書信', 
                '腓立比書信', '歌羅西書信', '帖撒羅尼迦書信 1', '帖撒羅尼迦書信 2', '提摩太書信 1', 
                '提摩太書信 2', '提多書信', '腓利門書信', '希伯來書信', '雅各書信', 
                '彼得書信 1', '彼得書信 2', '約翰書信 1', '約翰書信 2', '約翰書信 3', 
                '猶大書信', '默示錄']

    book_names_lat_abbr = ["mt", "mk", "lk", "iö", "sd", "lm", "1 k", "2 k", "kô", "yf",
                           "fl", "kl", "1 t", "2 t", "1d", "2d", "dt", "flm", "h", "nk",
                           "1 p", "2 p", "1 iö", "2 iö", "3 iö", "yd", "mz"]

    book_names_lat = ["mô-t'a djün foh-ing shü", "mô-k'o djün foh-ing shü", 
                      'lu-kô djün foh-ing shü', "iah-'ön djün foh-ing shü", 
                      "s-du 'ang-djün", 'lo-mô shü-sing', 
                      '1 ko-ling-to shü-sing', '2 ko-ling-to shü-sing', 
                      "kô-læh-t'a shü-sing", 'yi-feh-su shü-sing', 
                      'fi-lih-pi shü-sing', 'ko-lo-si shü-sing', 
                      "1 t'ih-sæh-lo-nyi-kô shü-sing", "2 t'ih-sæh-lo-nyi-kô shü-sing", 
                      "1 di-mo-t'a shü-sing", "2 di-mo-t'a shü-sing", 
                      'di-to shü-sing', 'fi-li-meng shü-sing', 
                      'hyi-pah-le shü-sing', 'ngô-kôh shü-sing', 
                      '1 pi-teh shü-sing', '2 pi-teh shü-sing', 
                      "1 iah-'ön shü-sing", "2 iah-'ön shü-sing", 
                      "3 iah-'ön shü-sing", 'yiu-da shü-sing', 
                      "iah-'ön-keh moh-z-loh"]


