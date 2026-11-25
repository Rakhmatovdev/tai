"""Small read-only tool surface; never eval, shell, arbitrary file paths or network."""
import ast
import math
import operator

TOOLS = [
    {'type':'function','function':{'name':'calculate','description':'Evaluate a bounded arithmetic expression.',
        'parameters':{'type':'object','properties':{'expression':{'type':'string'}},'required':['expression'],'additionalProperties':False}}},
    {'type':'function','function':{'name':'search_sources','description':'Search only document excerpts attached to this request.',
        'parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}}},
]


def calculate(expression):
    if not isinstance(expression,str) or len(expression)>200:
        raise ValueError('Ifoda juda uzun.')
    try:tree=ast.parse(expression,mode='eval')
    except SyntaxError as exc:raise ValueError('Arifmetik ifoda noto‘g‘ri.') from exc
    if sum(1 for _ in ast.walk(tree))>60:raise ValueError('Ifoda juda murakkab.')
    operations={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,
                ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):value=node.value
        elif isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=visit(node.operand)*(1 if isinstance(node.op,ast.UAdd) else -1)
        elif isinstance(node,ast.BinOp) and type(node.op) in operations:
            left,right=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.Pow) and (abs(right)>12 or abs(left)>1e12):
                raise ValueError('Daraja chegaradan katta.')
            value=operations[type(node.op)](left,right)
        else:raise ValueError('Faqat son va arifmetik amallardan foydalaning.')
        if type(value) not in (int,float) or abs(value)>1e100 or not math.isfinite(value):
            raise ValueError('Natija chegaradan katta.')
        return value
    try:return visit(tree.body)
    except (OverflowError,ZeroDivisionError,SyntaxError) as exc:raise ValueError('Arifmetik ifoda noto‘g‘ri.') from exc


def execute(name, arguments, sources):
    if not isinstance(arguments,dict):raise ValueError('Vosita argumentlari noto‘g‘ri.')
    if name=='calculate' and set(arguments)=={'expression'}:
        return {'result':calculate(arguments['expression'])}
    if name=='search_sources' and set(arguments)=={'query'}:
        query=arguments['query']
        if not isinstance(query,str) or not 1<=len(query)<=300:raise ValueError('Qidiruv matni noto‘g‘ri.')
        words=set(query.casefold().split())
        matches=[{'source':f'S{i+1}','text':row['text'][:1200]}
                 for i,row in enumerate(sources) if any(w in row['text'].casefold() for w in words)]
        return {'matches':matches[:4]}
    raise ValueError('Bu lokal vosita mavjud emas.')
