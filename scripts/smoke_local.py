"""Explicit local integration smoke using synthetic data; never reads user documents."""
import argparse
import base64
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from PyQt6.QtCore import QCoreApplication,QEventLoop
from brave_ollama_request import ChatRequest
from core.ollama_chat import Settings
from core.knowledge import KnowledgeStore
from core.local_tools import TOOLS,execute
from core.local_ocr import image_text,pdf_page


def request(app,model,messages,**kwargs):
    job=ChatRequest(Settings('http://127.0.0.1:11434',model,profile='economy',autostart=False),messages,**kwargs)
    loop=QEventLoop();result=[]
    job.finished.connect(lambda text,error,cancelled:(result.append((text,error,cancelled)),loop.quit()))
    job.start();loop.exec();metrics=dict(job.metrics);job.deleteLater();app.processEvents()
    text,error,cancelled=result[0]
    if error or cancelled:raise RuntimeError(error or 'cancelled')
    return text,metrics


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--vision',action='store_true');args=parser.parse_args()
    app=QCoreApplication([]);cancel=threading.Event();results={}
    with tempfile.TemporaryDirectory(prefix='brave-real-smoke-') as folder:
        root=Path(folder)
        from PIL import Image,ImageDraw,ImageFont
        image=Image.new('RGB',(1000,190),'white');draw=ImageDraw.Draw(image)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',46)
        draw.text((25,25),'Budjet: 42. Muddat: Dushanba.',font=font,fill='black')
        path=root/'plan.png';image.save(path)
        ocr=image_text(path,cancel);assert '42' in ocr and 'Dushanba' in ocr
        pdf=root/'scan.pdf';image.save(pdf,'PDF');scanned=pdf_page(pdf,0,cancel);assert '42' in scanned
        results['ocr']={'image':ocr.strip(),'scan_pdf':scanned.strip()}
        document=root/'project.txt'
        document.write_text('Ordinary background. '*80+'\nPayment must be received by Monday. The budget is 42 units.',encoding='utf-8')
        store=KnowledgeStore(root/'knowledge.db')
        try:
            settings=Settings('http://127.0.0.1:11434','llama3.2',profile='balanced',autostart=False)
            started=time.monotonic();store.index([document],settings,'embeddinggemma',cancel)
            sources,_=store.retrieve([document],'Pulni qaysi kuni topshirish kerak?',800,cancel,settings)
            assert 'Monday' in sources[0]['text']
            results['semantic']={'passed':True,'elapsed_s':round(time.monotonic()-started,2),'chunks':store.list()[0][2]}
        finally:store.close()
        schema={'type':'object','properties':{'budget':{'type':'string'},'deadline':{'type':'string'}},'required':['budget','deadline'],'additionalProperties':False}
        text,metrics=request(app,'llama3.2',[{'role':'user','content':'Extract JSON fields budget and deadline. Reference data: Budget is 42. Deadline is Monday. Return string values.'}],output_schema=schema)
        parsed=json.loads(text);assert parsed['budget']=='42';results['schema']={'passed':True,'metrics':metrics}
        calls=[]
        def tool(name,arguments):calls.append(name);return execute(name,arguments,[])
        text,metrics=request(app,'llama3.2',[{'role':'user','content':'Use the calculate tool to compute (1234 - 567) * 3. Then state the result.'}],tools=TOOLS,tool_handler=tool)
        assert '2001' in text and 'calculate' in calls
        results['tools']={'passed':True,'calls':calls,'metrics':metrics}
        if args.vision:
            text,metrics=request(app,'gemma4:12b',[{'role':'user','content':'Read the budget number in this image. Reply with the number only.'}],images=[base64.b64encode(path.read_bytes()).decode()])
            assert '42' in text;results['vision']={'passed':True,'answer':text,'metrics':metrics}
    target=Path(__file__).resolve().parent.parent/'design-preview/appearance/local-real-smoke.json'
    target.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
