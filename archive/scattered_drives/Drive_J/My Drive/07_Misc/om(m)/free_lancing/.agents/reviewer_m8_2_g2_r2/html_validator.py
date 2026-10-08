import pathlib
import re
from html.parser import HTMLParser

class TagBalanceValidator(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []
        
    def handle_starttag(self, tag, attrs):
        if tag.lower() not in self.VOID_TAGS:
            self.stack.append((tag.lower(), self.getpos()))
            
    def handle_endtag(self, tag):
        tag_l = tag.lower()
        if tag_l in self.VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{tag_l}> at line {self.getpos()[0]}")
            return
        last_tag, pos = self.stack.pop()
        if last_tag != tag_l:
            self.errors.append(f"Mismatched tag: expected </{last_tag}> (opened at line {pos[0]}), got </{tag_l}> at line {self.getpos()[0]}")

root = pathlib.Path('templates')
templates = ['general', 'cafe', 'transport', 'salon', 'retail', 'fitness', 'clinic']

print("=== HTML TAG BALANCE AUDIT ===")
for t in templates:
    html = (root / t / 'index.html').read_text(encoding='utf-8')
    parser = TagBalanceValidator()
    parser.feed(html)
    unclosed = [tag for tag, pos in parser.stack]
    print(f"[{t.upper()}] Errors: {len(parser.errors)}, Unclosed tags: {len(unclosed)} -> {unclosed[:5]}")
    if parser.errors:
        print(f"  First 3 errors: {parser.errors[:3]}")
