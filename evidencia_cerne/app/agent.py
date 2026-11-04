import json, os, re
import requests
from .knowledge import retrieve
from .ai_settings import current_settings

FIELDS = ['title','description','activity_date','location','participants','objective','results','indicators','competencies','conclusions']


def provider():
    selected = current_settings()['provider']
    return {'gemini': 'Gemini', 'openai': 'OpenAI'}.get(selected)


def _parse_json(raw):
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I)
    try: return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.S)
        if match: return json.loads(match.group())
        raise ValueError('O serviço de IA retornou um formato inválido.')


def generate(prompt):
    settings = current_settings()
    name = provider()
    if not name: raise ValueError('Configure a chave em Configurações da IA antes de usar a revisão inteligente.')
    try:
        if name == 'Gemini':
            model = settings['model']
            rsp = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                headers={'x-goog-api-key':settings['api_key']},
                json={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'temperature':0.2,'responseMimeType':'application/json'}}, timeout=65)
            rsp.raise_for_status()
            output = ''.join(p.get('text','') for p in rsp.json()['candidates'][0]['content']['parts'])
        else:
            model = settings['model']
            rsp = requests.post('https://api.openai.com/v1/chat/completions',
                headers={'Authorization':'Bearer '+settings['api_key']},
                json={'model':model,'messages':[{'role':'system','content':'Você escreve JSON válido e nunca inventa fatos.'},{'role':'user','content':prompt}],
                      'response_format':{'type':'json_object'},'temperature':0.2}, timeout=65)
            rsp.raise_for_status()
            output = rsp.json()['choices'][0]['message']['content']
        return _parse_json(output)
    except requests.exceptions.RequestException as exc:
        detail = ''
        if exc.response is not None:
            try: detail = str(exc.response.json().get('error',{}).get('message',''))[:220]
            except Exception: pass
        raise ValueError('Falha de comunicação com a IA. ' + (detail or str(exc)[:100])) from exc


def tidy(text):
    text = ' '.join(str(text or '').strip().split())
    if text and text[-1] not in '.!?': text += '.'
    return text[:12000]


def tidy_list(text):
    return '\n'.join(' '.join(part.split()) for part in str(text or '').splitlines() if part.strip())[:12000]


def rule_based_interpret(narrative):
    """Extract only explicitly spoken facts when the generative provider is disabled."""
    text = tidy(narrative)
    out = {field: '' for field in FIELDS}
    out['description'] = text
    out['title'] = 'Registro de atividade'
    low = text.lower()

    title = re.search(r'\b(?:atividade|oficina|aula|ação|reunião)\s+(?:chamada|intitulada|denominada)\s+["“]?([^"”.,;]+)', text, re.I)
    if title: out['title'] = title.group(1).strip()
    else:
        title = re.search(r'\b(?:realizamos|foi realizada|aconteceu|promovemos)\s+uma?\s+(oficina|aula|atividade|reunião)\s+(?:de|sobre|com)\s+([^.,;]+?)(?=\s+(?:com\s+\d+|na\s+escola|no\s+laboratório|no\s+ceet|para\s+os|com\s+alunos)|[.!?]|$)', text, re.I)
        if title: out['title'] = (title.group(1)+' de '+title.group(2)).strip()[:280]

    date = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text)
    if date:
        try:
            from datetime import date as datecls
            if date.group(1): year, month, day = int(date.group(1)), int(date.group(2)), int(date.group(3))
            else: year, month, day = int(date.group(6)), int(date.group(5)), int(date.group(4))
            out['activity_date'] = datecls(year,month,day).isoformat()
        except ValueError: pass
    if not out['activity_date']:
        months = ('janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro')
        match = re.search(r'\b(\d{1,2})\s+de\s+('+ '|'.join(months)+r')\s+de\s+(\d{4})\b',low)
        if match:
            try:
                from datetime import date as datecls
                out['activity_date']=datecls(int(match.group(3)),months.index(match.group(2))+1,int(match.group(1))).isoformat()
            except ValueError: pass

    loc = re.search(r'\b(?:na|no|em)\s+((?:escola|colégio|laboratório|auditório|sala|centro|instituto|ceet|ifes|incubadora)\s+[\wÀ-ÿ0-9ºª -]{2,70})', text, re.I)
    if loc:
        out['location'] = re.split(r'\s+(?:com|onde|para|durante|e\s+os)\b|[.,;]',loc.group(1),maxsplit=1,flags=re.I)[0].strip()

    people = re.search(r'\b(?:participaram|participaram da atividade|com a participação de|estiveram presentes)\s+([^.!?;]+)',text,re.I)
    if people:
        out['participants'] = people.group(1).strip()
    else:
        people = re.search(r'\bcom\s+(\d+\s+(?:alunos?|estudantes?|professores?|participantes?)(?:\s+e\s+\d+\s+(?:professores?|alunos?|estudantes?))?)',text,re.I)
        if people: out['participants']=people.group(1).strip()

    for pat in [r'\bo objetivo (?:foi|é|era)\s+([^.!?]+)', r'\bcom o objetivo de\s+([^.!?]+)',r'\ba finalidade (?:foi|é)\s+([^.!?]+)']:
        m=re.search(pat,text,re.I)
        if m: out['objective']=tidy(m.group(1));break
    for pat in [r'\b(?:os resultados foram|o resultado foi|como resultado|resultou em|conseguimos|foi concluíd[oa]|foi finalizad[oa])\s+([^.!?]+)',r'\b(?:foram desenvolvidos|foram criados|foram entregues|foram produzidos)\s+([^.!?]+)']:
        m=re.search(pat,text,re.I)
        if m: out['results']=tidy(m.group(0));break

    indicators=[]
    for match in re.finditer(r'\b(\d+)\s+(alunos?|estudantes?|professores?|projetos?|protótipos?|participantes?|equipes?|oficinas?|atividades?)\b',text,re.I):
        item=f'{match.group(2).capitalize()}: {match.group(1)}'
        if item not in indicators: indicators.append(item)
    out['indicators']='\n'.join(indicators)
    competency=re.search(r'\b(?:competências|habilidades)\s+(?:desenvolvidas|trabalhadas|abordadas)?\s*[:;]\s*([^.!?]+)',text,re.I)
    if competency: out['competencies']=tidy(competency.group(1))
    closing=re.search(r'\b(?:nas considerações finais|concluímos que)\s*[:;,]?\s*([^.!?]+)',text,re.I)
    if closing: out['conclusions']=tidy(closing.group(1))
    project=re.search(r'\b(?:projeto|projeto chamado)\s+([A-ZÀ-Ú][\wÀ-ÿ0-9 -]{2,60})',text)
    project_name=project.group(1).strip() if project else ''

    photo_groups=[]
    labels={1:r'(?:primeir[oa]\s+(?:registro|foto|fotografia)|registro\s+(?:1|um)|foto\s+(?:1|um))',
            2:r'(?:segund[oa]\s+(?:registro|foto|fotografia)|registro\s+(?:2|dois)|foto\s+(?:2|dois))',
            3:r'(?:terceir[oa]\s+(?:registro|foto|fotografia)|registro\s+(?:3|três|tres)|foto\s+(?:3|três|tres))'}
    markers=[]
    for pos,pattern in labels.items():
        for match in re.finditer(r'\b'+pattern+r'\b',text,re.I):markers.append((match.start(),match.end(),pos))
    markers.sort()
    for index,(start,after,pos) in enumerate(markers):
        end=markers[index+1][0] if index+1<len(markers) else len(text)
        segment=text[after:end].lstrip(' ,:;-')
        segment=re.split(r'[.!?]',segment,maxsplit=1)[0].strip()
        if segment and not any(x['position']==pos for x in photo_groups):
            photo_groups.append({'position':pos,'title':f'Registro {pos}','description':tidy(segment),'people':''})

    missing=[label for key,label in [('activity_date','Data'),('location','Local'),('participants','Participantes'),('results','Resultados alcançados')] if not out[key]]
    return {'fields':out,'groups':photo_groups,'missing':missing,'sources':[], 'project_name':project_name, 'mode':'basic',
            'notice':'Extração baseada em informações explícitas. Cadastre uma chave de IA para interpretar relatos mais livres.'}


def interpret_voice(narrative, db):
    if not provider(): return rule_based_interpret(narrative)
    sources = retrieve(db, narrative)
    prompt = f'''Você extrai informações de um relato em português brasileiro para uma plataforma de evidências.
Retorne APENAS um objeto JSON: {{"fields":{{"title":"","description":"","activity_date":"","location":"","participants":"","objective":"","results":"","indicators":"","competencies":"","conclusions":""}},"groups":[{{"position":1,"title":"","description":""}}],"missing":[""],"source_ids":[],"project_name":""}}.
Preencha também project_name se o usuário mencionar explicitamente o projeto, sem inventar.
Data em YYYY-MM-DD, se não houver data inequívoca deixe vazio. Não suponha local, data, nomes, números, indicadores ou resultados. Preencha indicadores apenas com números/dados narrados e competências apenas como competências trabalhadas explicitamente relatadas, não como habilidades comprovadas.
Você pode melhorar a escrita sem adicionar fatos. Separe trechos primeiro/segundo/terceiro registro em no máximo 3 grupos. Não afirme que fotos provam algo sem tê-las observado.
Relato: {narrative[:16000]}
Referências CERNE recuperadas (não as trate como fatos da atividade): {json.dumps(sources,ensure_ascii=False)[:6000]}'''
    ans = generate(prompt)
    fields = {k:str(ans.get('fields',{}).get(k,'') or '') for k in FIELDS}
    groups = [{**g,'position':int(g['position'])} for g in ans.get('groups',[]) if isinstance(g,dict) and str(g.get('position')) in ['1','2','3']][:3]
    return {'fields':fields,'groups':groups,'missing':ans.get('missing',[]),'sources':sources,'project_name':str(ans.get('project_name') or ''),'mode':'ai'}


def refine_activity(activity, db):
    facts = {k:getattr(activity,k,'') for k in FIELDS}
    groups = [{'position':g.position,'title':g.title,'description':g.description,'people':g.people,'number_of_photos':len(g.photos)} for g in activity.groups]
    sources = retrieve(db, ' '.join(str(x) for x in [activity.title,activity.description,activity.objective,activity.results, activity.project.name if activity.project else ''] ))
    if not provider():
        return {'mode':'basic','fields':{k:(tidy_list(v) if k in ('indicators','competencies') else tidy(v) if k in ('description','objective','results','conclusions') else v) for k,v in facts.items()},
            'groups':[{'position':g.position,'title':g.title,'description':tidy(g.description),'people':g.people} for g in activity.groups],
            'missing':[label for key,label in [('title','Título'),('description','Descrição'),('activity_date','Data'),('objective','Objetivo'),('results','Resultados')] if not facts.get(key)],
            'sources':sources,'notice':'Revisão textual básica. Configure uma chave de API para ter sugestões geradas por IA.'}
    prompt = f'''Você é assistente de documentação de incubadora. Responda em português do Brasil somente JSON.
Reescreva fielmente os fatos fornecidos, com linguagem institucional objetiva. É PROIBIDO inventar datas, quantidades, indicadores, resultados, ações, participantes, projetos, competências verificadas ou conteúdo de fotografias. Em indicators use uma linha por indicador comprovado; em competencies use uma linha por competência explicitamente trabalhada na ação, sem atribuir aprendizagem mensurada não comprovada.
Não trate a orientação da base CERNE como evidência de que a ação cumpriu uma prática. Alinhamento CERNE só se houver correspondência explícita; caso contrário registre como sugestão ou ausência de fonte. Não mencione normas ou códigos CERNE que não estejam literalmente nas fontes.
Retorne JSON: {{"fields":{{"title":"","description":"","activity_date":"","location":"","participants":"","objective":"","results":"","indicators":"","competencies":"","conclusions":""}},"groups":[{{"position":1,"title":"","description":"","people":""}}],"missing":["pergunta que falta responder"],"source_ids":["identificador"]}}.
O objetivo deve mostrar a finalidade concreta da ação e sua contribuição ao projeto, relacionando ao CERNE APENAS quando sustentado na base.
As considerações finais devem ser uma síntese dos fatos, sem afirmar ganhos inexistentes. Se o campo de resultados estiver vazio, preserve vazio e solicite dados.
Dados da atividade: {json.dumps(facts,ensure_ascii=False)}
Projeto: {activity.project.name if activity.project else 'Não informado'}
Registros: {json.dumps(groups,ensure_ascii=False)}
Trechos recuperados da base de conhecimento CERNE: {json.dumps(sources,ensure_ascii=False)[:12000]}'''
    ans = generate(prompt)
    return {'mode':'ai','fields':{k:str(ans.get('fields',{}).get(k, facts.get(k,'')) or '') for k in FIELDS},
            'groups':[{'position':g.get('position'),'title':str(g.get('title','')),'description':str(g.get('description','')),'people':str(g.get('people',''))} for g in ans.get('groups',[]) if isinstance(g,dict) and g.get('position') in [1,2,3]],
            'missing':ans.get('missing',[]),'sources':sources}


def complete_field(field, existing, spoken):
    """Only enrich information provided by the user; never fabricate evidence."""
    existing=str(existing or '').strip()
    spoken=str(spoken or '').strip()
    combined=' '.join(part for part in (existing,spoken) if part).strip()
    if not combined:
        return {'text':'','mode':'basic'}
    if not provider():
        return {'text':combined[:12000],'mode':'basic'}
    label={'description':'Descrição da atividade ou do registro fotográfico',
           'objective':'Objetivo','results':'Resultados','indicators':'Indicadores',
           'competencies':'Competências e habilidades','conclusions':'Considerações finais',
           'participants':'Participantes','people':'Participantes ou componentes',
           'title':'Título','location':'Local'}.get(field,field)
    prompt=f"""Você é um revisor de evidências institucionais. Retorne SOMENTE JSON com a chave text.
Campo: {label}
Texto confirmado pelo usuário: {json.dumps(existing,ensure_ascii=False)}
Complemento ditado agora: {json.dumps(spoken,ensure_ascii=False)}
Una o texto anterior com o complemento de modo natural. Corrija ortografia, pontuação e clareza.
Não exclua fatos do texto anterior, não acrescente fatos, datas, números, resultados,
nomes ou práticas CERNE não declarados. Não transforme objetivos em resultados atingidos.
Se o campo contém lista de indicadores, mantenha um indicador por linha.
Se é título, local ou participantes, preserve nomes próprios e não crie informações novas.
Responda somente JSON com a chave text, contendo todo o texto reescrito."""
    result=generate(prompt)
    revised=str(result.get('text') or '').strip()
    return {'text':(revised or combined)[:12000],'mode':'ai'}

def describe_photo_groups(activity):
    """Opt-in multimodal photo description; uploads never leave host without user action."""
    import base64, io
    from pathlib import Path
    from PIL import Image
    from .database import DATA_DIR
    if not provider(): raise ValueError('Configure a chave em Configurações da IA antes de analisar fotografias.')
    settings = current_settings()
    photos=[]
    for group in activity.groups:
        for item in list(group.photos)[:1]:
            fp=DATA_DIR/'uploads'/item.filename
            if not fp.exists(): continue
            with Image.open(fp) as im:
                im.thumbnail((1100,1100)); buf=io.BytesIO();im.convert('RGB').save(buf,format='JPEG',quality=78)
            photos.append((group.position,base64.b64encode(buf.getvalue()).decode('ascii')))
    if not photos:raise ValueError('Adicione fotografias a pelo menos um registro antes de analisar.')
    context={'title':activity.title,'description':activity.description,'objective':activity.objective,
        'groups':[{'position':g.position,'title':g.title,'description':g.description,'people':g.people,'photos':sum(p==g.position for p,_ in photos)} for g in activity.groups]}
    instruction=f'''Você está descrevendo fotos de uma atividade institucional. Responda somente JSON no formato
{{"groups":[{{"position":1,"title":"","description":"","people":""}}],"missing":[""],"source_ids":[]}}.
Descreva APENAS o que é visível, em linguagem técnica e clara. Não atribua nomes, identidades, intenções, aprendizados, realizações ou números que não sejam verificáveis visualmente. Não presuma que o conteúdo de uma foto comprova resultado do projeto.
O usuário anexou imagens na ordem indicada, cada uma precedida por 'Grupo X'. Crie uma descrição única por grupo com base nas fotografias e no contexto sem inventar. Preserve grupos mesmo que uma foto não possa ser interpretada. Não altere fatos já informados nos demais campos.
Contexto declarado pelo usuário: {json.dumps(context,ensure_ascii=False)}'''
    if provider()=='Gemini':
        model=os.getenv('GEMINI_MODEL','gemini-2.5-flash')
        parts=[{'text':instruction}]
        for pos,raw in photos:
            parts.append({'text':f'Grupo {pos}, fotografia seguinte:'})
            parts.append({'inline_data':{'mime_type':'image/jpeg','data':raw}})
        try:
            r=requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                headers={'x-goog-api-key':settings['api_key']},
                json={'contents':[{'parts':parts}],'generationConfig':{'responseMimeType':'application/json','temperature':0.1}},timeout=100)
            r.raise_for_status()
            out=''.join(x.get('text','') for x in r.json()['candidates'][0]['content']['parts'])
        except requests.exceptions.RequestException as exc:raise ValueError('Falha ao analisar fotos com o Gemini: '+str(exc)[:150])
    else:
        model=os.getenv('OPENAI_MODEL','gpt-4o-mini')
        contents=[{'type':'text','text':instruction}]
        for pos,raw in photos:
            contents.append({'type':'text','text':f'Grupo {pos}, fotografia seguinte:'})
            contents.append({'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+raw,'detail':'low'}})
        try:
            r=requests.post('https://api.openai.com/v1/chat/completions',
                headers={'Authorization':'Bearer '+settings['api_key']},
                json={'model':model,'messages':[{'role':'user','content':contents}], 'response_format':{'type':'json_object'},'temperature':0.1}, timeout=100)
            r.raise_for_status();out=r.json()['choices'][0]['message']['content']
        except requests.exceptions.RequestException as exc:raise ValueError('Falha ao analisar fotos com a OpenAI: '+str(exc)[:150])
    data=_parse_json(out)
    return {'mode':'ai','fields':{},'groups':[{'position':int(g.get('position')),'title':str(g.get('title','')),
        'description':str(g.get('description','')),'people':str(g.get('people',''))} for g in data.get('groups',[])
        if isinstance(g,dict) and str(g.get('position','')) in ['1','2','3']],
        'missing':data.get('missing',[]),'sources':[],'notice':'As imagens foram analisadas pelo serviço externo configurado. Revise as descrições propostas antes de usar.'}
