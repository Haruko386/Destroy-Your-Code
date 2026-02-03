# core/obfuscate.py
import ast
import random
import string
import builtins
import keyword

# 1. 基础保护
COMMON_LIBRARIES_ATTRS = {
    'join', 'split', 'strip', 'replace', 'append', 'extend', 'pop', 'remove', 'insert',
    'index', 'count', 'sort', 'reverse', 'copy', 'clear', 'update', 'get', 'keys', 'values', 'items',
    'read', 'write', 'open', 'close', 'flush', 'seek', 'tell', 'readline', 'readlines',
    'lower', 'upper', 'startswith', 'endswith', 'find', 'rfind', 'format', 'encode', 'decode',
    'exists', 'isdir', 'isfile', 'listdir', 'walk', 'makedirs', 'mkdir', 'rmdir', 'remove', 'unlink',
    'match', 'search', 'findall', 'sub', 'compile', 'group', 'start', 'end', 'span',
    'datetime', 'date', 'time', 'now', 'utcnow', 'timestamp',
    'args', 'kwargs', 'self', 'cls', 'root', 'parent', 'name', 'path', 'main',
    'add_argument', 'parse_args', 'set_defaults', 'description', 'help', 'type', 'default', 'choices', 'required'
}

SAFE_NAMES = set(dir(builtins)) | set(keyword.kwlist) | {
    'self', 'cls', 'args', 'kwargs', 'super',
    '__init__', '__name__', '__main__', '__str__', '__repr__', '__doc__', '__file__',
    'True', 'False', 'None'
} | COMMON_LIBRARIES_ATTRS

def random_case(name):
    if len(name) < 2: return name
    for _ in range(5):
        new_name = "".join(c.upper() if random.random() > 0.5 else c.lower() for c in name)
        if new_name != name: return new_name
    return name

def random_string(length=4):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

class FStringConverter(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        new_values = []
        format_args = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                text = part.value.replace('{', '{{').replace('}', '}}')
                new_values.append(text)
            elif isinstance(part, ast.FormattedValue):
                fmt = ":" + part.format_spec.values[0].value if part.format_spec else ""
                new_values.append("{" + fmt + "}")
                format_args.append(part.value)
        format_string = "".join(new_values)
        new_node = ast.Call(
            func=ast.Attribute(value=ast.Constant(value=format_string), attr='format', ctx=ast.Load()),
            args=format_args, keywords=[]
        )
        return ast.copy_location(new_node, node)

class RecursiveScanner(ast.NodeVisitor):
    def __init__(self, global_map):
        self.global_map = global_map

    def _add_name(self, name):
        if name in SAFE_NAMES or name in self.global_map: return
        
        if random.random() < 0.2:
            new_name = random_string(max(3, len(name)//2))
        else:
            new_name = random_case(name)
            if new_name == name or new_name in SAFE_NAMES: new_name = random_string(5)
        
        self.global_map[name] = new_name

    def visit_ClassDef(self, node):
        self._add_name(node.name)
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name): self._add_name(target.id)
            elif isinstance(stmt, ast.AnnAssign):
                 if isinstance(stmt.target, ast.Name): self._add_name(stmt.target.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if not node.name.startswith('__'): self._add_name(node.name)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Store) and isinstance(node.value, ast.Name) and node.value.id == 'self':
            self._add_name(node.attr)

class GlobalRenameTransformer(ast.NodeTransformer):
    def __init__(self, global_map, file_safe_list):
        self.global_map = global_map
        self.local_map = {} 
        self.safe_list = file_safe_list

    def get_new_name(self, old_name, is_definition=False):
        if old_name in self.safe_list: return old_name
        if old_name in self.global_map: return self.global_map[old_name]
        if old_name in self.local_map: return self.local_map[old_name]
        
        if is_definition:
            if random.random() < 0.2:
                new_name = random_string(max(3, len(old_name)//2))
            else:
                new_name = random_case(old_name)
            self.local_map[old_name] = new_name
            return new_name
        return old_name

    def visit_FunctionDef(self, node):
        if not node.name.startswith('__'):
            if node.name in self.global_map: node.name = self.global_map[node.name]
            else: node.name = self.get_new_name(node.name, is_definition=True)
        for arg in node.args.args:
            arg.arg = self.get_new_name(arg.arg, is_definition=True)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        if node.name in self.global_map: node.name = self.global_map[node.name]
        else: node.name = self.get_new_name(node.name, is_definition=True)
        self.generic_visit(node)
        return node

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            node.id = self.get_new_name(node.id, is_definition=True)
        elif isinstance(node.ctx, ast.Load):
            node.id = self.get_new_name(node.id, is_definition=False)
        return node
    
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'args':
            self.generic_visit(node)
            return node
        if node.attr in self.global_map and node.attr not in self.safe_list:
            node.attr = self.global_map[node.attr]
        self.generic_visit(node)
        return node

    def visit_Call(self, node):
        for keyword in node.keywords:
            if keyword.arg and keyword.arg in self.global_map:
                keyword.arg = self.global_map[keyword.arg]
        self.generic_visit(node)
        return node

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name in self.global_map:
                alias.name = self.global_map[alias.name]
        self.generic_visit(node)
        return node
    
    def _visit_comprehension(self, node):
        # 1. 先处理 generators (for ... in ...)
        for generator in node.generators:
            self.visit(generator) # 这会触发 visit_Name(Store)，把循环变量(f)加入 local_map
        
        # 2. 再处理推导式主体 (key: value 或 elt)
        if hasattr(node, 'key'): self.visit(node.key)
        if hasattr(node, 'value'): self.visit(node.value)
        if hasattr(node, 'elt'): self.visit(node.elt)
        
        return node

    def visit_ListComp(self, node): return self._visit_comprehension(node)
    def visit_SetComp(self, node): return self._visit_comprehension(node)
    def visit_GeneratorExp(self, node): return self._visit_comprehension(node)
    def visit_DictComp(self, node): return self._visit_comprehension(node)


def squeeze_lines(code):
    return "\n".join([line for line in code.splitlines() if line.strip()])

def scan_global_definitions(code) -> dict:
    global_map = {}
    try:
        tree = ast.parse(code)
        scanner = RecursiveScanner(global_map)
        scanner.visit(tree)
    except: pass
    return global_map

def obfuscate_code(code, global_map={}):
    try:
        tree = ast.parse(code)
    except SyntaxError: return code

    tree = FStringConverter().visit(tree)

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names: imported_names.add(alias.name.split('.')[0])
        if isinstance(node, ast.ImportFrom):
             if node.module: imported_names.add(node.module.split('.')[0])
             for alias in node.names:
                 if alias.name not in global_map: imported_names.add(alias.name)

    file_safe_list = SAFE_NAMES | imported_names

    transformer = GlobalRenameTransformer(global_map, file_safe_list)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)

    return squeeze_lines(ast.unparse(tree))