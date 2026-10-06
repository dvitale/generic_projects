"""Import exported Maia PGNs without collecting third-party credentials."""
import io,re
from urllib.parse import urlparse
import chess.pgn
from fastapi import HTTPException
from pydantic import BaseModel,Field,ValidationError
from typing import Literal


def maia_level(name):
    match=re.fullmatch(r'maia(?:[ _-]kdd)?[ _-]+(\d{3,4})',name.strip(),re.I)
    return int(match[1]) if match and 600<=int(match[1])<=2600 else None


def origin(headers):
    return 'Maia online' if urlparse(headers.get('Site','')).hostname in {'maiachess.com','www.maiachess.com'} else 'PGN importato'


class BatchInput(BaseModel):
    pgn:str=Field(min_length=1,max_length=1000000)
    username:str=Field(default='',max_length=80)
    color:Literal['auto','w','b']='auto'
    analyze:bool=True


def install(app,import_one,input_type,database,find_game,queue_analysis):
    @app.post('/api/import/batch')
    def batch(body:BatchInput):
        stream=io.StringIO(body.pgn.lstrip('\ufeff'));parsed=[]
        while True:
            try:game=chess.pgn.read_game(stream)
            except (ValueError,IndexError) as exc:raise HTTPException(422,'PGN non leggibile: controlla il file esportato.') from exc
            if game is None:break
            parsed.append(game)
            if len(parsed)>20:raise HTTPException(422,'Importa al massimo 20 partite alla volta.')
        if not parsed:raise HTTPException(422,'Nessuna partita PGN trovata.')
        results=[]
        for index,game in enumerate(parsed,1):
            try:
                if game.errors:raise HTTPException(422,'Mosse non valide: partita non importata.')
                color=body.color
                if color=='auto':
                    names=[game.headers.get('White',''),game.headers.get('Black','')]
                    matches=[i for i,n in enumerate(names) if body.username and n.casefold()==body.username.strip().casefold()]
                    bots=[i for i,n in enumerate(names) if maia_level(n) is not None]
                    if len(matches)==1:color='w' if matches[0]==0 else 'b'
                    elif not body.username and len(bots)==1:color='b' if bots[0]==0 else 'w'
                    else:raise HTTPException(422,'Colore non riconosciuto: indica il tuo nome nel PGN oppure scegli Bianco/Nero.')
                text=game.accept(chess.pgn.StringExporter(headers=True,variations=False,comments=True))
                with database() as con:before={r[0] for r in con.execute('SELECT id FROM games')}
                saved=import_one(input_type(pgn=text,color=color))
                job_id=None;analysis_error=None
                if body.analyze and not saved['analysis']:
                    try:
                        with database() as con:row=dict(find_game(con,saved['id']))
                        job_id=queue_analysis(row,automatic=True)['jobId']
                    except Exception:analysis_error='Partita salvata; avvia Analizza partita dalla revisione.'
                results.append({'index':index,'id':saved['id'],'title':saved['title'],'color':color,
                  'origin':origin(dict(game.headers)),'duplicate':saved['id'] in before,'jobId':job_id,'analysisError':analysis_error})
            except HTTPException as exc:results.append({'index':index,'error':str(exc.detail)})
            except ValidationError:results.append({'index':index,'error':'Partita troppo grande: esporta il PGN senza annotazioni estese.'})
        return {'results':results,'imported':sum('id' in r and not r['duplicate'] for r in results),
                'duplicates':sum(r.get('duplicate',False) for r in results),'failed':sum('error' in r for r in results)}
