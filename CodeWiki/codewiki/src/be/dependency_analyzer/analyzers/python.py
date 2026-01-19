import ast
import logging
import warnings
from typing import List, Tuple, Optional, Dict, Set
from pathlib import Path
import sys
import os


from codewiki.src.be.dependency_analyzer.models.core import Node, CallRelationship

logger = logging.getLogger(__name__)


class PythonASTAnalyzer(ast.NodeVisitor):

    def __init__(self, file_path: str, content: str, repo_path: Optional[str] = None):
        """
        Initialize the Python AST analyzer.

        Args:
            file_path: Path to the Python file being analyzed
            content: Raw content of the Python file
            repo_path: Repository root path for calculating relative paths
        """
        self.file_path = file_path
        self.repo_path = repo_path
        self.content = content
        self.lines = content.splitlines()
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []
        self.current_class_name: str | None = None
        self.current_function_name: str | None = None
        
        self.top_level_nodes = {}
        
        # 新增：导入映射 - 用于跨文件依赖解析
        self.imports: Dict[str, str] = {}  # alias/name -> full module path
        self.from_imports: Dict[str, str] = {}  # imported name -> full path (module.name)
        self.import_statements: List[Dict] = []  # 存储所有import语句信息
    
    def _get_relative_path(self) -> str:
        """Get relative path from repo root."""
        if self.repo_path:
            return os.path.relpath(self.file_path, self.repo_path)
        return str(self.file_path)

    def _get_module_path(self) -> str:
        try:
            relative_path = self._get_relative_path()
            path = relative_path
            for ext in ['.py', '.pyx']:
                if path.endswith(ext):
                    path = path[:-len(ext)]
                    break
            return path.replace('/', '.').replace('\\', '.')
        except:
            return str(self.file_path).replace('/', '.').replace('\\', '.')
    
    def _get_component_id(self, name: str) -> str:
        """Generate dot-separated component ID."""
        module_path = self._get_module_path()
        if self.current_class_name:
            return f"{module_path}.{self.current_class_name}.{name}"
        else:
            return f"{module_path}.{name}"

    def generic_visit(self, node):
        """Override generic_visit to continue AST traversal."""
        super().generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """解析 import 语句并建立导入映射"""
        for alias in node.names:
            module_name = alias.name
            local_name = alias.asname or alias.name
            # 存储完整模块路径
            self.imports[local_name] = module_name
            self.import_statements.append({
                "type": "import",
                "module": module_name,
                "alias": alias.asname,
                "line": node.lineno
            })
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """解析 from ... import ... 语句"""
        module = node.module or ""
        level = node.level  # 相对导入级别
        
        # 处理相对导入
        if level > 0:
            # 获取当前模块路径
            current_module = self._get_module_path()
            parts = current_module.split('.')
            # 根据level计算基础模块路径
            if level <= len(parts):
                base_module = '.'.join(parts[:-level]) if level < len(parts) else ''
                if module:
                    module = f"{base_module}.{module}" if base_module else module
                else:
                    module = base_module
        
        for alias in node.names:
            imported_name = alias.name
            local_name = alias.asname or alias.name
            
            if imported_name == "*":
                # from module import * - 记录但无法精确追踪
                self.import_statements.append({
                    "type": "from_import_star",
                    "module": module,
                    "line": node.lineno
                })
            else:
                full_path = f"{module}.{imported_name}" if module else imported_name
                self.from_imports[local_name] = full_path
                self.import_statements.append({
                    "type": "from_import",
                    "module": module,
                    "name": imported_name,
                    "alias": alias.asname,
                    "full_path": full_path,
                    "line": node.lineno
                })
        self.generic_visit(node)

    def _resolve_import_reference(self, name: str) -> Optional[str]:
        """
        解析名称引用，尝试通过import语句找到完整路径。
        
        Args:
            name: 代码中使用的名称（可能是alias或原始名称）
            
        Returns:
            完整的模块路径，或None如果无法解析
        """
        # 先检查 from ... import ... 的导入
        if name in self.from_imports:
            return self.from_imports[name]
        
        # 检查是否是模块导入后的属性访问 (如 os.path.join)
        parts = name.split('.')
        if parts[0] in self.imports:
            # 替换第一部分为完整模块路径
            full_module = self.imports[parts[0]]
            return '.'.join([full_module] + parts[1:])
        
        return None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition and add to top-level nodes."""

        base_classes = [self._extract_base_class_name(base) for base in node.bases]
        base_classes = [name for name in base_classes if name is not None]
        
        # 提取装饰器
        decorators = self._extract_decorators(node)
        
        component_id = f"{self._get_module_path()}.{node.name}"
        relative_path = self._get_relative_path()
        
        class_node = Node(
            id=component_id,
            name=node.name,
            component_type="class",
            file_path=str(self.file_path),
            relative_path=relative_path,
            source_code="\n".join(self.lines[node.lineno - 1 : node.end_lineno or node.lineno]),
            start_line=node.lineno,
            end_line=node.end_lineno,
            has_docstring=bool(ast.get_docstring(node)),
            docstring=ast.get_docstring(node) or "",
            parameters=decorators if decorators else None,  # 复用parameters存储装饰器
            node_type="class",
            base_classes=base_classes if base_classes else None,
            class_name=None,
            display_name=f"class {node.name}",
            component_id=component_id
        )
        self.nodes.append(class_node)
        self.top_level_nodes[node.name] = class_node

        # 增强：处理基类依赖关系
        for base_name in base_classes:
            if base_name in self.top_level_nodes:
                # 同文件内的基类
                self.call_relationships.append(CallRelationship(
                    caller=component_id,
                    callee=f"{self._get_module_path()}.{base_name}",
                    call_line=node.lineno,
                    is_resolved=True
                ))
            else:
                # 尝试通过import解析跨文件基类
                resolved_base = self._resolve_import_reference(base_name)
                if resolved_base:
                    self.call_relationships.append(CallRelationship(
                        caller=component_id,
                        callee=resolved_base,
                        call_line=node.lineno,
                        is_resolved=False  # 标记为待外部解析
                    ))
                else:
                    # 无法解析，仍记录原始名称
                    self.call_relationships.append(CallRelationship(
                        caller=component_id,
                        callee=base_name,
                        call_line=node.lineno,
                        is_resolved=False
                    ))

        self.current_class_name = node.name
        self.generic_visit(node)
        self.current_class_name = None
    
    def _extract_decorators(self, node) -> List[str]:
        """提取类或函数的装饰器信息"""
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                dec_name = self._get_call_name(decorator)
                if dec_name:
                    decorators.append(dec_name)
            elif isinstance(decorator, ast.Call):
                # 带参数的装饰器，如 @decorator(arg)
                if isinstance(decorator.func, ast.Name):
                    decorators.append(f"{decorator.func.id}(...)")
                elif isinstance(decorator.func, ast.Attribute):
                    dec_name = self._get_call_name(decorator.func)
                    if dec_name:
                        decorators.append(f"{dec_name}(...)")
        return decorators
    
    def _extract_base_class_name(self, base):
        """Extract base class name from AST node."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            parts = []
            node = base
            while isinstance(node, ast.Attribute):
                parts.append(node.attr)
                node = node.value
            if isinstance(node, ast.Name):
                parts.append(node.id)
            return ".".join(reversed(parts))
        return None

    def _process_function_node(self, node: ast.FunctionDef | ast.AsyncFunctionDef):
        """Process function definition - only add to nodes if it's top-level."""

        if not self.current_class_name:
            component_id = f"{self._get_module_path()}.{node.name}"
            relative_path = self._get_relative_path()
            
            # 提取参数列表（包含类型注解）
            parameters = self._extract_parameters_with_types(node)
            
            # 提取装饰器
            decorators = self._extract_decorators(node)
            
            # 提取返回类型
            return_type = None
            if node.returns:
                try:
                    return_type = ast.unparse(node.returns)
                except:
                    return_type = str(node.returns)
            
            # 构建增强的函数签名作为display_name
            is_async = isinstance(node, ast.AsyncFunctionDef)
            async_prefix = "async " if is_async else ""
            display_name = f"{async_prefix}function {node.name}"
            if return_type:
                display_name += f" -> {return_type}"
            
            func_node = Node(
                id=component_id,
                name=node.name,
                component_type="async_function" if is_async else "function",
                file_path=str(self.file_path),
                relative_path=relative_path,
                source_code="\n".join(self.lines[node.lineno - 1 : node.end_lineno or node.lineno]),
                start_line=node.lineno,
                end_line=node.end_lineno,
                has_docstring=bool(ast.get_docstring(node)),
                docstring=ast.get_docstring(node) or "",
                parameters=parameters,
                node_type="async_function" if is_async else "function",
                base_classes=decorators if decorators else None,  # 复用base_classes存储装饰器
                class_name=None,
                display_name=display_name,
                component_id=component_id
            )
            if self._should_include_function(func_node):
                self.nodes.append(func_node)
                self.top_level_nodes[node.name] = func_node
                
                # 分析类型注解中引用的类型，建立依赖关系
                self._extract_type_dependencies(node, component_id)

        self.current_function_name = node.name
        self.generic_visit(node)
        self.current_function_name = None
    
    def _extract_parameters_with_types(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """提取函数参数，包含类型注解"""
        params = []
        for arg in node.args.args:
            if arg.annotation:
                try:
                    type_str = ast.unparse(arg.annotation)
                    params.append(f"{arg.arg}: {type_str}")
                except:
                    params.append(arg.arg)
            else:
                params.append(arg.arg)
        return params
    
    def _extract_type_dependencies(self, node: ast.FunctionDef | ast.AsyncFunctionDef, caller_id: str):
        """从类型注解中提取依赖关系"""
        type_refs = set()
        
        # 提取参数类型
        for arg in node.args.args:
            if arg.annotation:
                self._collect_type_refs(arg.annotation, type_refs)
        
        # 提取返回类型
        if node.returns:
            self._collect_type_refs(node.returns, type_refs)
        
        # 为每个类型引用创建依赖关系
        for type_ref in type_refs:
            # 尝试解析导入
            resolved = self._resolve_import_reference(type_ref)
            if resolved:
                self.call_relationships.append(CallRelationship(
                    caller=caller_id,
                    callee=resolved,
                    call_line=node.lineno,
                    is_resolved=False
                ))
            elif type_ref in self.top_level_nodes:
                self.call_relationships.append(CallRelationship(
                    caller=caller_id,
                    callee=f"{self._get_module_path()}.{type_ref}",
                    call_line=node.lineno,
                    is_resolved=True
                ))
    
    def _collect_type_refs(self, node: ast.expr, refs: Set[str]):
        """递归收集类型注解中的类型引用"""
        if isinstance(node, ast.Name):
            # 过滤内置类型
            if node.id not in {'int', 'str', 'float', 'bool', 'None', 'Any', 'Optional', 
                               'List', 'Dict', 'Set', 'Tuple', 'Union', 'Callable'}:
                refs.add(node.id)
        elif isinstance(node, ast.Attribute):
            # 处理如 typing.Optional 这样的情况
            name = self._get_call_name(node)
            if name:
                refs.add(name)
        elif isinstance(node, ast.Subscript):
            # 处理 List[SomeType], Optional[SomeType] 等
            self._collect_type_refs(node.value, refs)
            self._collect_type_refs(node.slice, refs)
        elif isinstance(node, ast.Tuple):
            for elt in node.elts:
                self._collect_type_refs(elt, refs)
        elif isinstance(node, ast.BinOp):
            # 处理 Type1 | Type2 (Python 3.10+)
            self._collect_type_refs(node.left, refs)
            self._collect_type_refs(node.right, refs)

    def _should_include_function(self, func: Node) -> bool:
        if func.name.startswith("_test_"):
            return False
        return True

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition and extract function information."""
        self._process_function_node(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition and extract function information."""
        self._process_function_node(node)

    def visit_Call(self, node: ast.Call):
        """Visit function call nodes and record relationships between top-level nodes."""

        if self.current_class_name or (self.current_function_name and not self.current_class_name):
            call_name = self._get_call_name(node.func)
            if call_name:
                if self.current_class_name:
                    caller_id = f"{self._get_module_path()}.{self.current_class_name}"
                else:
                    caller_id = f"{self._get_module_path()}.{self.current_function_name}"
                
                # 增强：多层次解析调用目标
                callee_id = None
                is_resolved = False
                
                # 1. 检查是否是同文件内的调用
                if call_name in self.top_level_nodes:
                    callee_id = f"{self._get_module_path()}.{call_name}"
                    is_resolved = True
                else:
                    # 2. 尝试通过import解析跨文件调用
                    resolved = self._resolve_import_reference(call_name)
                    if resolved:
                        callee_id = resolved
                        is_resolved = False  # 标记为需要外部验证
                    else:
                        # 3. 检查是否是类的方法调用 (self.method / cls.method)
                        parts = call_name.split('.')
                        if len(parts) >= 2:
                            obj_name = parts[0]
                            if obj_name in ('self', 'cls') and self.current_class_name:
                                # 类内方法调用
                                callee_id = f"{self._get_module_path()}.{self.current_class_name}"
                                is_resolved = True
                            elif obj_name in self.from_imports or obj_name in self.imports:
                                # 导入对象的方法调用
                                resolved = self._resolve_import_reference(call_name)
                                if resolved:
                                    callee_id = resolved
                        
                        # 4. 无法解析，使用原始名称
                        if not callee_id:
                            callee_id = call_name
                
                relationship = CallRelationship(
                    caller=caller_id,
                    callee=callee_id,
                    call_line=node.lineno,
                    is_resolved=is_resolved
                )
                self.call_relationships.append(relationship)

        self.generic_visit(node)

    def _get_call_name(self, node) -> str | None:
        """
        Extract function name from a call node.
        Handles simple names, attributes (obj.method), and filters built-ins.
        """
        PYTHON_BUILTINS = {
            "print", "len", "str", "int", "float", "bool", "list", "dict", "tuple", "set",
            "range", "enumerate", "zip", "isinstance", "hasattr", "getattr", "setattr",
            "open", "super", "__import__", "type", "object", "Exception", "ValueError",
            "TypeError", "KeyError", "IndexError", "AttributeError", "ImportError",
            "max", "min", "sum", "abs", "round", "sorted", "reversed", "filter", "map",
            "any", "all", "next", "iter", "callable", "repr", "format", "exec", "eval"
        }

        if isinstance(node, ast.Name):
            if node.id in PYTHON_BUILTINS:
                return None
            return node.id
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id in PYTHON_BUILTINS:
                    return None
                return f"{node.value.id}.{node.attr}"
            elif isinstance(node.value, ast.Attribute):
                base_name = self._get_call_name(node.value)
                if base_name:
                    return f"{base_name}.{node.attr}"
            return node.attr
        return None

    def analyze(self):
        """Analyze the Python file and extract functions and relationships."""

        try:
            # Suppress SyntaxWarnings about invalid escape sequences in source code
            # These warnings come from regex patterns like '\(' or '\.' in the analyzed files
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=SyntaxWarning)
                tree = ast.parse(self.content)
            
            # 先遍历一次收集所有import语句
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.visit_Import(node)
                elif isinstance(node, ast.ImportFrom):
                    self.visit_ImportFrom(node)
            
            # 再进行完整遍历
            self.visit(tree)

            logger.debug(
                f"Python analysis complete for {self.file_path}: {len(self.nodes)} nodes, "
                f"{len(self.call_relationships)} relationships, {len(self.import_statements)} imports"
            )
        except SyntaxError as e:
            logger.warning(f"Could not parse {self.file_path}: {e}")
        except Exception as e:
            logger.error(f"Error analyzing {self.file_path}: {e}", exc_info=True)
    
    def get_import_info(self) -> Dict[str, any]:
        """获取导入信息，供外部使用"""
        return {
            "imports": dict(self.imports),
            "from_imports": dict(self.from_imports),
            "statements": self.import_statements
        }


def analyze_python_file(
    file_path: str, content: str, repo_path: Optional[str] = None
) -> Tuple[List[Node], List[CallRelationship]]:
    """
    Analyze a Python file and return classes, functions, methods, and relationships.

    Args:
        file_path: Path to the Python file
        content: Content of the Python file
        repo_path: Repository root path for calculating relative paths

    Returns:
        tuple: (nodes, call_relationships)
    """

    analyzer = PythonASTAnalyzer(file_path, content, repo_path)
    analyzer.analyze()
    return analyzer.nodes, analyzer.call_relationships


def analyze_python_file_with_imports(
    file_path: str, content: str, repo_path: Optional[str] = None
) -> Tuple[List[Node], List[CallRelationship], Dict[str, any]]:
    """
    Analyze a Python file and return nodes, relationships, and import information.
    
    Args:
        file_path: Path to the Python file
        content: Content of the Python file
        repo_path: Repository root path for calculating relative paths

    Returns:
        tuple: (nodes, call_relationships, import_info)
    """
    analyzer = PythonASTAnalyzer(file_path, content, repo_path)
    analyzer.analyze()
    return analyzer.nodes, analyzer.call_relationships, analyzer.get_import_info()

