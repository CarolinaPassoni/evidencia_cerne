'use strict';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtDate=s=>s?new Date(s+'T12:00:00').toLocaleDateString('pt-BR'):'Sem data';
const fmtTime=s=>s?new Date(s).toLocaleString('pt-BR'):'-';
const fields=['title','description','activity_date','location','participants','objective','results','indicators','competencies','conclusions','project_id','status'];
const fieldLabels={title:'Título',description:'Descrição da atividade',activity_date:'Data',location:'Local',participants:'Participantes',objective:'Objetivo',results:'Resultados alcançados',indicators:'Indicadores alcançados',competencies:'Competências e habilidades',conclusions:'Considerações finais'};
const state={user:null,csrf:'',provider:null,view:'dashboard',activity:null,projects:[],people:[],templates:[],knowledge:[],pendingAI:null,autosave:null,saving:false,savePromise:null,dirty:false,voice:null,recording:false,voiceNarrative:'',voiceBusy:false,filter:{},currentTemplate:''};
const root=$('#content');
let toastTimer;
function toast(message,error=false){const e=$('#toast');e.textContent=message;e.style.background=error?'#9b3044':'#183656';e.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>e.classList.remove('show'),4500)}
async function api(path,options={}){
  const method=(options.method||'GET').toUpperCase();
  const headers={'X-CSRF-Token':state.csrf,...options.headers};
  let body=options.body;
  if(body&&!(body instanceof FormData)&&typeof body!=='string'){headers['Content-Type']='application/json';body=JSON.stringify(body)}
  const attempts=method==='GET'?2:1;
  for(let attempt=0;attempt<attempts;attempt++){
    let r;
    try{
      r=await fetch('/api'+path,{...options,body,credentials:'same-origin',cache:'no-store',headers});
    }catch{
      if(attempt+1<attempts)continue;
      throw Error(method==='GET'?'Não foi possível conectar ao servidor. Aguarde alguns segundos e tente novamente.':'O salvamento não foi confirmado. Mantenha esta página aberta para preservar o texto e tente novamente.');
    }
    if(r.status===401){if(state.user)showLogin();throw Error('Sua sessão terminou. Faça login novamente.')}
    if([502,503,504].includes(r.status)&&attempt+1<attempts)continue;
    const raw=await r.text();
    let data;
    try{data=JSON.parse(raw)}catch{
      const action=method==='GET'?'Tente novamente em alguns segundos.':'A operação não foi confirmada. Mantenha esta página aberta e confira o registro antes de tentar novamente.';
      throw Error('O servidor retornou uma resposta inesperada (HTTP '+r.status+', '+method+' /api'+path.split('?')[0]+'). '+action);
    }
    if(!r.ok){
      let message=typeof data.detail==='string'?data.detail:'Não foi possível concluir a operação.';
      if(r.status===429)message='Muitas solicitações. Aguarde um pouco e tente novamente.';
      throw Error(message+' (HTTP '+r.status+')');
    }
    return data;
  }
}
function setLoading(b,label='Carregando...'){root.innerHTML=`<div class="container"><div class="panel"><p class="muted">${esc(label)}</p></div></div>`}
function renderPage(title,subtitle,inside,extra=''){const names={dashboard:'Visão geral',activities:'Atividades',editor:'Editar evidência',documents:'Documentos',knowledge:'Base CERNE',projects:'Projetos',people:'Pessoas e itens',templates:'Modelos Word',settings:'Configurar IA'};$('#page-name').textContent=names[state.view]||title;root.innerHTML=`<div class="container"><div class="hero-head"><div><p class="eyebrow">EVIDÊNCIA +</p><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>${extra}</div>${inside}</div>`;document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===state.view));}
function showLogin(){setMenu(false);stopVoice(true);state.user=null;state.csrf='';$('#login-screen').classList.remove('hidden');$('#application').classList.add('hidden')}
async function init(){try{const u=await api('/auth/me');loggedIn(u)}catch{showLogin()}}
async function loggedIn(u){state.voiceNarrative='';state.user=u;state.csrf=u.csrf;state.provider=u.provider;$('#login-screen').classList.add('hidden');$('#application').classList.remove('hidden');$('#user-name').textContent=u.name;$('#avatar').textContent=(u.name||'A')[0].toUpperCase();$('#ai-settings-nav').classList.toggle('hidden',u.role!=='admin');$('#provider-name').textContent=u.provider?`IA ${u.provider} configurada`:'Modo básico ativo';$('#provider-caption').textContent=u.provider?'Sugestões com IA e base CERNE':'Conecte uma chave para ativar IA';$('#provider-dot').classList.toggle('online',!!u.provider);try{await loadRefs();await navigate('dashboard')}catch(e){toast(e.message,true)}}
async function loadRefs(){const [projects,people,templates]=await Promise.all([api('/projects'),api('/people'),api('/templates')]);state.projects=projects;state.people=people;state.templates=templates;state.currentTemplate=state.currentTemplate||templates.find(t=>t.layout==='reference')?.id||templates[0]?.id||'';}
async function navigate(v,id){stopVoice(true);if((state.dirty||state.saving)&&state.activity){try{await saveNow()}catch(e){toast('Não foi possível salvar: '+e.message,true);return}}state.view=v;setMenu(false);setLoading();try{switch(v){case 'dashboard':await dashboard();break;case 'activities':await listActivities();break;case 'editor':if(id){state.activity=await api('/activities/'+id)}else if(!state.activity){state.activity=await api('/activities',{method:'POST'})}renderEditor();break;case 'documents':await listDocuments();break;case 'knowledge':await listKnowledge();break;case 'projects':await listProjects();break;case 'people':await listPeople();break;case 'templates':await listTemplates();break;case 'settings':await aiSettingsPage();break;default:await dashboard()}}catch(e){root.innerHTML=`<div class="container"><div class="panel">${esc(e.message)}</div></div>`;toast(e.message,true)}}
async function newEvidence(){try{if(state.dirty||state.saving)await saveNow();state.voiceNarrative='';state.activity=await api('/activities',{method:'POST'});await navigate('editor',state.activity.id);toast('Novo registro criado. Os dados serão salvos automaticamente.')}catch(e){toast(e.message,true)}}
const statusBadge=s=>s==='approved'?'<span class="pill green">✓ Aprovada</span>':'<span class="pill amber">● Rascunho</span>';
function activityListItem(a){return `<div class="activity-row"><div class="row-icon">▤</div><div><b>${esc(a.title)}</b><small>${esc(a.project_name||'Sem projeto')} · ${fmtDate(a.activity_date)}</small></div>${statusBadge(a.status)}<button class="arrow-button" title="Abrir" data-act="open" data-id="${a.id}">→</button></div>`}
async function dashboard(){const data=await api('/overview');renderPage('Sua documentação, organizada.','Acompanhe o que já foi registrado e continue de onde parou.',`<div class="stats">${[['Atividades registradas',data.activities,'▤','Total de atividades'],['Evidências aprovadas',data.approved,'✓','Prontas para exportar'],['Projetos cadastrados',data.projects,'◇','Em acompanhamento'],['Documentos gerados',data.documents,'▣','Word e PDF']].map(([name,num,ico,note])=>`<div class="stat-card"><div class="stat-top"><span>${esc(name)}</span><span class="stat-icon">${ico}</span></div><div class="stat-number">${num}</div><div class="stat-footer">${note}</div></div>`).join('')}</div><div class="grid-2"><section class="panel"><div class="panel-head"><div><h3>Atividades recentes</h3><p>Seus últimos registros, em um só lugar.</p></div><button class="btn small" data-view="activities">Ver todas</button></div>${data.recent.length?data.recent.map(activityListItem).join(''):'<div class="empty-card"><span class="icon">▤</span><h3>Nenhuma evidência por aqui</h3><p>Crie seu primeiro registro para começar.</p><button class="btn primary" data-act="new">Criar evidência</button></div>'}</section><div><section class="feature-card"><small>ASSISTENTE DE ESCRITA</small><h3>Transforme um relato simples em um registro completo.</h3><p>Digite ou conte por voz o que aconteceu. Revise o texto, reúna as fotos e gere um Word editável.</p><button class="btn" data-act="new">Começar agora →</button></section><div class="panel" style="margin-top:21px"><div class="panel-head"><h3>Base de conhecimento</h3><span class="pill">${data.knowledge} referências</span></div><p class="helper-text">Adicione documentos CERNE e orientações institucionais. As referências recuperadas serão usadas na elaboração dos textos.</p><button class="btn small" data-view="knowledge">Gerenciar base CERNE →</button></div></div></div>`)}
function selectProjects(value='',empty='Selecione um projeto'){return `<option value="">${esc(empty)}</option>${state.projects.map(p=>`<option value="${p.id}" ${p.id===value?'selected':''}>${esc(p.name)}</option>`).join('')}`}
async function listActivities(){const all=await api('/activities');state.activity=null;renderPage('Todas as atividades','Pesquise, abra ou continue um registro já iniciado.',`<section class="panel"><div class="filters"><label class="searchbox">Pesquisar<input id="filter-q" placeholder="Título, descrição, participante..." value="${esc(state.filter.q||'')}"></label><label>Projeto<select id="filter-project">${selectProjects(state.filter.project||'','Todos os projetos')}</select></label><label>De<input type="date" id="filter-from" value="${esc(state.filter.from||'')}"></label><label>Até<input type="date" id="filter-to" value="${esc(state.filter.to||'')}"></label><button class="btn" data-act="search">Filtrar</button></div></section><section id="activity-results"><div class="subhead">${all.length} registro(s)</div>${all.length?`<div class="list-cards">${all.map(a=>`<article class="evidence-card"><div class="flex-between">${statusBadge(a.status)}<small class="muted">${fmtDate(a.activity_date)}</small></div><h3>${esc(a.title)}</h3><p>${esc(a.description||'Registro ainda sem descrição.')}</p><div class="details"><span>${esc(a.project_name||'Sem projeto')}</span><button data-act="open" data-id="${a.id}">Abrir registro →</button></div></article>`).join('')}</div>`:`<div class="empty-card"><span class="icon">▤</span><h3>Comece pela primeira atividade</h3><button class="btn primary" data-act="new">Criar evidência</button></div>`}</section>`,'<button class="btn primary" data-act="new">+ Nova evidência</button>')}
async function applyFilters(){state.filter={q:$('#filter-q').value,project:$('#filter-project').value,from:$('#filter-from').value,to:$('#filter-to').value};const query=new URLSearchParams({q:state.filter.q,project_id:state.filter.project,date_from:state.filter.from,date_to:state.filter.to});const all=await api('/activities?'+query);$('#activity-results').innerHTML=`<div class="subhead">${all.length} registro(s) encontrado(s)</div>${all.length?`<div class="list-cards">${all.map(a=>`<article class="evidence-card"><div class="flex-between">${statusBadge(a.status)}<small class="muted">${fmtDate(a.activity_date)}</small></div><h3>${esc(a.title)}</h3><p>${esc(a.description)}</p><div class="details"><span>${esc(a.project_name||'Sem projeto')}</span><button data-act="open" data-id="${a.id}">Abrir registro →</button></div></article>`).join('')}</div>`:'<div class="empty-card"><h3>Nenhum resultado para os filtros.</h3></div>'}`}
function micButton(label='Ditar este campo'){return `<button type="button" class="mic-button" data-act="voice-field" title="${esc(label)}" aria-label="${esc(label)}">🎙</button>`}
function inputField(key,label,opts={}){const a=state.activity;const val=a[key]||'';return `<div class="field"><div class="dictation-label"><label for="f-${key}">${label}</label>${micButton('Ditar '+label)}</div>${opts.textarea?`<textarea id="f-${key}" data-field="${key}" rows="${opts.rows||4}" placeholder="${esc(opts.placeholder||'Escreva aqui...')}">${esc(val)}</textarea>`:`<input id="f-${key}" data-field="${key}" type="${opts.type||'text'}" placeholder="${esc(opts.placeholder||'')}" value="${esc(val)}">`}</div>`}
function groupPanel(g){return `<section class="group-panel"><div class="group-top"><div class="round-index">${g.position}</div><strong>Registro fotográfico ${g.position}</strong><span>${g.photos.length} foto(s)</span></div><div class="field-row"> <div class="field"><div class="dictation-label"><label>Identificação do registro</label>${micButton()}</div><input data-group="${g.position}" data-group-field="title" placeholder="Ex.: Montagem dos componentes" value="${esc(g.title)}"></div><div class="field"><div class="dictation-label"><label>Participantes ou componentes</label>${micButton()}</div><input data-group="${g.position}" data-group-field="people" placeholder="Ex.: Alunos do módulo II" value="${esc(g.people)}"></div></div><div class="field"><div class="dictation-label"><label>Descrição das fotografias</label>${micButton()}</div><textarea data-group="${g.position}" data-group-field="description" rows="3" placeholder="O que as imagens registram?">${esc(g.description)}</textarea></div><label class="dropzone"><span class="upload-symbol">⇪</span><span><strong>Adicionar fotografias</strong><small>JPG, PNG ou WebP, até 12 MB por foto</small></span><input class="hidden" data-upload="${g.position}" type="file" multiple accept="image/jpeg,image/png,image/webp"></label>${g.photos.length?`<div class="photos-grid">${g.photos.map((p,i)=>`<div class="photo-tile"><img src="${p.url}" alt="${esc(p.name)}" loading="lazy"><div class="photo-name" title="${esc(p.name)}">${esc(p.name)}</div><label class="photo-label">Descrição da foto${micButton()}<textarea rows="2" data-photo-id="${p.id}" data-photo-field="description" maxlength="3000" placeholder="O que esta foto mostra?">${esc(p.description||'')}</textarea></label><label class="photo-label">Participantes/componentes${micButton()}<input data-photo-id="${p.id}" data-photo-field="people" maxlength="1000" placeholder="Opcional" value="${esc(p.people||'')}"></label><div class="photo-controls"><button title="Mover para esquerda" data-act="move-photo" data-id="${p.id}" data-direction="up" ${i===0?'disabled':''}>←</button><button title="Mover para direita" data-act="move-photo" data-id="${p.id}" data-direction="down" ${i===g.photos.length-1?'disabled':''}>→</button><button title="Excluir" data-act="remove-photo" data-id="${p.id}" style="color:#bb475e">×</button></div></div>`).join('')}</div>`:''}</section>`}
function htmlPaper(){const a=state.activity;if(!a)return '';const t=state.templates.find(x=>x.id===state.currentTemplate)||state.templates[0];if(t?.layout==='reference')return htmlReferencePaper(a);return `<div class="paper"><div class="paper-kicker">${esc(t?.institution||'EVIDÊNCIAS INSTITUCIONAIS')}</div><h3>${esc(t?.subtitle||'RELATÓRIO DE EVIDÊNCIA')}</h3><p style="text-align:center;font-weight:bold">${esc(a.title)}</p><h4>1. Identificação da atividade</h4><p><b>Data:</b> ${fmtDate(a.activity_date)}<br><b>Local:</b> ${esc(a.location||'Não informado')}<br><b>Participantes:</b> ${esc(a.participants||'Não informado')}<br><b>Projeto:</b> ${esc(state.projects.find(x=>x.id===a.project_id)?.name||'Não informado')}</p><h4>2. Descrição da atividade</h4><p>${esc(a.description||'Não informado.')}</p><h4>3. Objetivo</h4><p>${esc(a.objective||'Não informado.')}</p><h4>4. Registros fotográficos</h4>${a.groups.filter(g=>g.photos.length||g.title||g.description||g.people).map(g=>`<p><b>Registro ${g.position} | ${esc(g.title||'Fotografias')}</b></p><div>${g.photos.map(x=>`<img src="${x.url}" alt="${esc(x.name)}">`).join('')}</div><p><b>Descrição:</b> ${esc(g.description||'Não informada.')}</p>${g.people?`<p><b>Participantes/componentes:</b> ${esc(g.people)}</p>`:''}`).join('')||'<p>Sem fotografias.</p>'}<h4>5. Resultados alcançados</h4><p>${esc(a.results||'Não informado.')}</p><h4>6. Considerações finais</h4><p>${esc(a.conclusions||'Não informado.')}</p></div>`}

function splitEvidenceLines(s){const v=String(s||'').trim();return (v.includes('\n')?v.split(/\r?\n/):v.split(';')).map(x=>x.trim().replace(/^[•●*\-]\s*/,'' )).filter(Boolean)}
function htmlReferencePaper(a){
  const ttl=(a.title||'Atividade sem título').trim();
  const date=fmtDate(a.activity_date);
  const title=a.activity_date&&!ttl.includes(date)?`${ttl} (${date})`:ttl;
  const people=String(a.participants||'').replace(/;/g,'\n').split('\n').map(s=>s.trim()).filter(Boolean);
  const bullet=s=>splitEvidenceLines(s).map(x=>`<li>${esc(x)}</li>`).join('')||'<p>Não informado.</p>';
  const groups=[1,2,3].map(pos=>{const g=a.groups.find(x=>x.position===pos);return `<h4>Registro ${pos}</h4>${g?.photos?.length?g.photos.map(x=>`<img class="reference-photo" src="${x.url}" alt="${esc(x.name)}">${x.description?`<p><b>Descrição da fotografia:</b> ${esc(x.description)}</p>`:''}${x.people?`<p><b>Participantes/componentes na foto:</b> ${esc(x.people)}</p>`:''}`).join(''):'<p><i>Nenhuma fotografia anexada.</i></p>'}${g?.description?`<p><b>Descrição do registro:</b> ${esc(g.description)}</p>`:''}${g?.people?`<p><b>Participantes/componentes:</b> ${esc(g.people)}</p>`:''}`}).join('');
  return `<div class="paper paper-reference"><p class="reference-title">${esc(title)}</p><h4>Descrição:</h4><p>${esc(a.description||'Não informado.')}</p>${groups}<h4>Participantes dessa ação:</h4>${people.length?people.map(x=>`<p class="reference-person">${esc(x)}</p>`).join(''):'<p>Não informado.</p>'}<h4>Objetivo:</h4><p>${esc(a.objective||'Não informado.')}</p><h4>Resultados:</h4><p>${esc(a.results||'Não informado.')}</p><h4>Indicadores alcançados:</h4><ul>${bullet(a.indicators)}</ul><h4>Competências e habilidades:</h4><ul>${bullet(a.competencies)}</ul></div>`;
}
function renderEditor(){const a=state.activity;if(!a)return;state.dirty=false;$('#save-indicator').textContent='';renderPage(a.status==='approved'?'Evidência aprovada':'Produção de evidência','Preencha, revise e exporte. Tudo fica guardado automaticamente.',`<div class="editor-headline"><div class="flex">${statusBadge(a.status)}<span class="pill">${fmtDate(a.activity_date)}</span></div><div class="actions"><button class="btn small" data-act="duplicate">Duplicar</button><button class="btn small" data-act="history">Histórico</button><button class="btn small danger" data-act="delete-activity">Excluir</button></div></div><div class="editor-layout"><div class="editor-column"><div class="ai-banner"><div class="ai-bubble">✦</div><div><strong>${state.provider?'Seu assistente está pronto para revisar':'Revisão básica disponível'}</strong><p>${state.provider?'A IA sugere textos com base no seu relato e nas referências CERNE recuperadas. Você aprova as mudanças.':'Sem chave de IA, o sistema organiza os dados e realiza uma revisão simples, sem gerar conteúdo novo.'}</p></div><button class="btn primary small" data-act="ai-refine">✦ Revisar texto</button></div><section class="panel"><div class="section-title"><div class="section-index">01</div><h3>Comece pelo relato</h3></div><div class="voice-head"><span class="form-label">Conte o que aconteceu, escrevendo ou falando</span><span class="pill" id="voice-status">● Pronto para ouvir</span></div><textarea class="form-control" rows="5" id="voice-text" placeholder="Exemplo: Hoje realizamos uma oficina com 20 alunos. No primeiro registro, os participantes organizaram os componentes..." style="width:100%;line-height:1.65"></textarea><div class="voice-toolbar"><button class="btn teal" data-act="voice">🎙 Falar e preencher tudo</button><button class="btn soft" data-act="interpret">✦ Interpretar relato</button><small class="note">Fale tudo de uma vez e pare a gravação. Os campos serão preenchidos automaticamente. Revise o conteúdo antes de aprovar. Requer navegador compatível e permissão para o microfone.</small></div><p id="voice-fill-report" class="helper-text" role="status"></p></section><section class="panel"><div class="section-title"><div class="section-index">02</div><h3>Identificação da atividade</h3></div>${inputField('title','Título da atividade',{placeholder:'Ex.: Oficina de empreendedorismo'})}<div class="field-row"><div class="field"><div class="dictation-label"><label for="f-activity_date">Data de realização</label>${micButton("Ditar data de realização")}</div><input id="f-activity_date" data-field="activity_date" type="date" value="${esc(a.activity_date)}"></div><div class="field"><div class="dictation-label"><label>Projeto vinculado</label>${micButton("Ditar nome do projeto")}</div><select data-field="project_id">${selectProjects(a.project_id,'Sem projeto vinculado')}</select></div></div>${inputField('location','Local de realização',{placeholder:'Escola, cidade ou endereço'})}${inputField('participants','Participantes envolvidos',{textarea:true,rows:2,placeholder:'Pessoas, equipes ou turmas'})}${state.people.filter(x=>x.kind!=='component').length?`<div class="flex" style="margin:-7px 0 20px"><select class="form-control" id="add-person-select" style="width:auto;flex:1;min-width:180px"><option value="">Buscar pessoa cadastrada...</option>${state.people.filter(x=>x.kind!=='component').map(x=>`<option value="${esc(x.name)}">${esc(x.name)}</option>`).join('')}</select><button class="btn small" data-act="insert-person">+ Inserir participante</button></div>`:''}${inputField('description','Descrição geral',{textarea:true,rows:5,placeholder:'Descreva as ações realizadas, sem acrescentar fatos não comprovados.'})}${inputField('objective','Objetivo da atividade',{textarea:true,rows:3,placeholder:'Qual foi a finalidade concreta desta ação?'})}${inputField('results','Resultados alcançados',{textarea:true,rows:4,placeholder:'Registre apenas entregas e resultados verificados.'})}${inputField('indicators','Indicadores alcançados',{textarea:true,rows:4,placeholder:'Um indicador por linha. Ex.: Estudantes participantes: 20'})}${inputField('competencies','Competências e habilidades',{textarea:true,rows:5,placeholder:'Uma competência por linha. Ex.: Trabalho em equipe: colaboração durante a oficina.'})}<p class="note">Indicadores e competências só devem registrar informações observadas ou relatadas. Uma linha por item.</p></section><section class="panel"><div class="section-title"><div class="section-index">03</div><h3>Registros fotográficos</h3><small>Até 3 grupos</small></div><p class="helper-text">É possível anexar várias imagens em cada grupo. Use as setas para definir a ordem em que aparecem no Word.</p>${state.provider?`<div class="flex" style="margin-bottom:16px"><button class="btn soft small" data-act="ai-photos">✦ Sugerir descrições pelas fotos</button><span class="note">As imagens serão enviadas ao provedor de IA após sua confirmação.</span></div>`:''}${a.groups.map(groupPanel).join('')}</section><section class="panel"><div class="section-title"><div class="section-index">04</div><h3>Considerações finais</h3></div>${inputField('conclusions','Síntese final',{textarea:true,rows:4,placeholder:'Importância da ação e contribuições demonstradas pelos registros.'})}<div class="flex-between"><div><strong style="font-size:13px">Situação do registro</strong><p class="note">A aprovação é necessária antes de exportar o documento.</p></div><button class="btn ${a.status==='approved'?'':'primary'}" data-act="toggle-approval">${a.status==='approved'?'Voltar ao rascunho':'✓ Aprovar evidência'}</button></div></section></div><aside class="panel preview-panel"><div class="panel-head"><div><h3>Prévia do documento</h3><p>Como seu registro ficará no papel.</p></div><span class="pill">A4</span></div><div class="field"><label>Modelo visual</label><select id="template-selector">${state.templates.map(x=>`<option value="${x.id}" ${x.id===state.currentTemplate?'selected':''}>${esc(x.name)}</option>`).join('')}</select></div><div class="paper-shell" id="document-preview">${htmlPaper()}</div><div class="preview-actions"><button class="btn primary" data-act="export" data-format="docx">↓ Word .docx</button><button class="btn" data-act="export" data-format="pdf">↓ PDF</button></div><p class="note">A prévia é simplificada. O Word final utiliza margens, estilos e tamanhos de imagem definidos no modelo.</p></aside></div>`,'');if($('#voice-text'))$('#voice-text').value=state.voiceNarrative;}
function touch(){state.dirty=true;$('#save-indicator').textContent='Alterações pendentes';clearTimeout(state.autosave);state.autosave=setTimeout(()=>saveNow().catch(e=>toast(e.message,true)),950)}
async function saveNow(){
  clearTimeout(state.autosave);
  if(state.saving){if(state.savePromise)await state.savePromise;if(state.dirty)return saveNow();return}
  if(!state.dirty||!state.activity)return;
  state.saving=true;$('#save-indicator').textContent='Salvando...';
  const a=state.activity;const payload={};
  fields.forEach(x=>payload[x]=a[x]??'');payload.project_id=a.project_id||null;
  payload.groups=a.groups.map(g=>({position:g.position,title:g.title,description:g.description,people:g.people}));
  state.dirty=false;
  state.savePromise=api('/activities/'+a.id,{method:'PATCH',body:payload});
  try{
    const result=await state.savePromise;
    if(state.activity===a){
      const wasApproved=a.status==='approved';a.status=result.status;
      if(wasApproved&&result.status==='draft'){
        const button=document.querySelector('[data-act="toggle-approval"]');
        if(button){button.textContent='✓ Aprovar evidência';button.classList.add('primary')}
        const badge=document.querySelector('.editor-headline .pill.green');if(badge)badge.outerHTML=statusBadge('draft');
        toast('O registro voltou para rascunho após a edição. Aprove novamente antes de exportar.');
      }
    }
    $('#save-indicator').textContent='✓ Salvo automaticamente';
    return result;
  }catch(e){state.dirty=true;$('#save-indicator').textContent='Falha ao salvar';throw e}
  finally{state.saving=false;state.savePromise=null;if(state.dirty)state.autosave=setTimeout(()=>saveNow().catch(e=>toast(e.message,true)),950)}
}
function refreshPreview(){const el=$('#document-preview');if(el)el.innerHTML=htmlPaper()}
async function reloadEditor(){if(!state.activity)return;const id=state.activity.id;state.activity=await api('/activities/'+id);renderEditor()}
async function uploadPhotos(pos,files){if(!files?.length)return;if(files.length>15){toast('Selecione até 15 fotos por envio.',true);return}try{if(state.dirty)await saveNow();const form=new FormData();[...files].forEach(f=>form.append('files',f));state.activity=await api(`/activities/${state.activity.id}/photos/${pos}`,{method:'POST',body:form});renderEditor();toast(`${files.length} foto(s) adicionada(s).`)}catch(e){toast(e.message,true)}}
async function moveOrDeletePhoto(id,action,dir){try{if(state.dirty)await saveNow();if(action==='remove'){if(!confirm('Excluir esta fotografia?'))return;await api('/photos/'+id,{method:'DELETE'})}else{await api('/photos/'+id+'/move',{method:'POST',body:{direction:dir}})}await reloadEditor();toast('Fotografias atualizadas.')}catch(e){toast(e.message,true)}}
function modal(title,body,footer='',wide=false){$('#modal-root').innerHTML=`<div class="dialog-backdrop" role="presentation"><section class="dialog ${wide?'wide':''}" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="dialog-head"><h2>${esc(title)}</h2><button class="dialog-close" data-act="close-modal" aria-label="Fechar">×</button></div>${body}<div class="dialog-footer">${footer||'<button class="btn" data-act="close-modal">Fechar</button>'}</div></section></div>`}
function closeModal(){$('#modal-root').innerHTML='';state.pendingAI=null}
async function refineWithAI(){try{await saveNow();toast('Consultando informações e referências...');const data=await api('/activities/'+state.activity.id+'/ai/refine',{method:'POST'});reviewSuggestion(data)}catch(e){toast(e.message,true)}}
async function describePhotos(){if(!confirm('As fotografias serão enviadas ao provedor de IA configurado para análise. Não envie imagens sem autorização dos envolvidos. Deseja continuar?'))return;try{await saveNow();const data=await api('/activities/'+state.activity.id+'/ai/photos',{method:'POST'});reviewSuggestion(data)}catch(e){toast(e.message,true)}}
async function interpretNarrative(){const text=$('#voice-text')?.value.trim();if(!text){toast('Digite ou fale seu relato primeiro.',true);return}try{toast('Analisando o relato...');const data=await api('/ai/interpret',{method:'POST',body:{text}});reviewSuggestion(data)}catch(e){toast(e.message,true)}}
function reviewSuggestion(data){state.pendingAI=data;const a=state.activity;const diffs=Object.entries(data.fields||{}).filter(([k,v])=>fieldLabels[k]&&String(v||'').trim()&&String(v||'')!==String(a[k]||''));const groups=data.groups||[];modal(data.mode==='ai'?'Sugestões da inteligência artificial':'Revisão básica do texto',`<div class="notice-box ${data.mode==='basic'?'warn':''}">${esc(data.notice||(data.mode==='ai'?'Revise o conteúdo antes de aplicá-lo. Sugestões não são comprovações de fatos.':'Modo básico: os campos são organizados sem geração de texto por modelo de IA.'))}</div>${diffs.map(([k,v])=>`<div class="comparison-row"><h4>${esc(fieldLabels[k])}</h4><div class="compare-grid"><div><label>Antes</label>${esc(a[k]||'Campo vazio')}</div><div><label>Sugestão</label>${esc(v)}</div></div></div>`).join('')}${groups.length?`<h3 style="margin-top:20px">Registros fotográficos</h3>${groups.map(g=>`<div class="comparison-row"><h4>Registro ${g.position}</h4><p class="helper-text">${esc(g.description||'Sem descrição sugerida.')}</p></div>`).join('')}`:''}${data.missing?.length?`<div class="notice-box warn"><b>Informações a complementar:</b><ul>${data.missing.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:''}${data.sources?.length?`<h3>Referências recuperadas na base CERNE</h3>${data.sources.map(s=>`<p class="helper-text"><b>${esc(s.title)}</b> ${s.verified?'(verificada)':'(não verificada)'}: ${esc(s.text.slice(0,220))}...</p>`).join('')}`:'<p class="note">Nenhuma referência CERNE relacionada foi recuperada. Não confunda ausência de base com alinhamento comprovado.</p>'}`,`<button class="btn" data-act="close-modal">Cancelar</button><button class="btn primary" data-act="apply-ai">Aplicar sugestões</button>`,true)}
async function applySuggestion(){const d=state.pendingAI;if(!d||!state.activity)return;for(const [k,v] of Object.entries(d.fields||{})){if(fields.includes(k)&&typeof v==='string'&&v.trim())state.activity[k]=v}for(const row of d.groups||[]){const g=state.activity.groups.find(x=>x.position===row.position);if(!g)continue;for(const k of ['title','description','people'])if(typeof row[k]==='string'&&row[k].trim())g[k]=row[k]}closeModal();touch();await saveNow();renderEditor();toast('Sugestões aplicadas. Confira os dados antes da aprovação.')}
async function toggleApproval(){if(state.dirty)await saveNow();const a=state.activity;if(a.status!=='approved'){let missing=['title','description','objective','results'].filter(k=>!a[k]?.trim());if(missing.length){toast('Antes de aprovar, preencha: '+missing.map(k=>fieldLabels[k]).join(', '),true);return}if(!confirm('Confirma que os textos e as fotografias representam fatos reais e foram revisados?'))return}a.status=a.status==='approved'?'draft':'approved';touch();await saveNow();renderEditor();toast(a.status==='approved'?'Evidência aprovada. Agora você pode exportar.':'Evidência devolvida ao rascunho.')}
async function exportDocument(format){try{await saveNow();const data=await api(`/activities/${state.activity.id}/generate`,{method:'POST',body:{format,template_id:state.currentTemplate}});const link=document.createElement('a');link.href=data.download;link.download='evidencia.'+format;document.body.appendChild(link);link.click();link.remove();toast('Documento '+format.toUpperCase()+' gerado e guardado no histórico.')}catch(e){toast(e.message,true)}}
async function showHistory(){try{await saveNow();const [rows,docs]=await Promise.all([api('/activities/'+state.activity.id+'/history'),api('/documents')]);const mydocs=docs.filter(x=>x.activity_id===state.activity.id);modal('Histórico da evidência',`<h3>Documentos gerados</h3>${mydocs.map(x=>`<p><a href="/api/documents/${x.id}/download" download>${esc(x.format.toUpperCase())} · ${fmtTime(x.created_at)} ↓</a></p>`).join('')||'<p class="note">Nenhum documento gerado.</p>'}<h3 style="margin-top:20px">Alterações registradas</h3><ul class="history-list">${rows.map(x=>`<li><b>${esc(({created:'Atividade criada',updated:'Campos alterados',photos_uploaded:'Fotos adicionadas',photo_deleted:'Foto excluída',photos_reordered:'Fotos reorganizadas',duplicated:'Atividade duplicada',document_generated:'Documento gerado'})[x.action]||x.action)}</b><span>${fmtTime(x.timestamp)}</span></li>`).join('')}</ul>`)}catch(e){toast(e.message,true)}}
async function deleteCurrent(){if(!confirm('Excluir esta atividade, suas fotografias e seus documentos? Essa ação não pode ser desfeita.'))return;try{await api('/activities/'+state.activity.id,{method:'DELETE'});state.activity=null;await navigate('activities');toast('Atividade excluída.')}catch(e){toast(e.message,true)}}
async function duplicateCurrent(){try{await saveNow();const a=await api('/activities/'+state.activity.id+'/duplicate',{method:'POST'});state.activity=a;renderEditor();toast('Cópia criada. Revise a data e os resultados.')}catch(e){toast(e.message,true)}}
let recognition=null, speechContext=null;
function stopVoice(silent=false){
  if(speechContext&&silent)speechContext.cancelled=true;
  if(recognition){try{recognition.stop()}catch{} }
}
function normalizeSpeech(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim()}
function spokenDate(s){
  const input=normalizeSpeech(s);let day,month,year;
  let hit=input.match(/\b(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{4})\b/);
  if(hit){day=+hit[1];month=+hit[2];year=+hit[3]}
  else {const names=['janeiro','fevereiro','marco','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'];
    hit=input.match(/\b(\d{1,2})\s+de\s+([a-z]+)\s+(?:de\s+)?(\d{4})\b/);
    if(hit){day=+hit[1];month=names.indexOf(hit[2])+1;year=+hit[3]}
  }
  if(!hit&&/^(hoje|dia de hoje)$/.test(input)){const now=new Date();day=now.getDate();month=now.getMonth()+1;year=now.getFullYear()}
  if(!day||!month||!year)return null;
  const test=new Date(year,month-1,day);
  return test.getFullYear()===year&&test.getMonth()+1===month&&test.getDate()===day?`${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`:null;
}
function updateDictatedField(el,spoken){
  if(!el||!el.isConnected)return;
  if(el.tagName==='SELECT'){
    const exact=[...el.options].find(o=>normalizeSpeech(o.textContent)===normalizeSpeech(spoken));
    const partial=exact||[...el.options].find(o=>normalizeSpeech(o.textContent).includes(normalizeSpeech(spoken)) && o.value);
    if(!partial){toast('Não encontrei esse projeto cadastrado. Selecione na lista ou cadastre o projeto.',true);return}
    el.value=partial.value;
  }else if(el.type==='date'){
    const formatted=spokenDate(spoken);
    if(!formatted){toast('Não consegui entender a data. Fale, por exemplo, 03 de novembro de 2026.',true);return}
    el.value=formatted;
  }else el.value=spoken;
  el.dispatchEvent(new Event('input',{bubbles:true}));
  el.dispatchEvent(new Event('change',{bubbles:true}));
  if(state.view==='editor'&&state.activity)toast('Ditado inserido e salvo no campo.');
}
function startVoice(mode,target=null){
  const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Speech){toast('Reconhecimento de voz indisponível neste navegador. Use Chrome ou Edge atualizado, com microfone autorizado.',true);return}
  if(recognition){stopVoice();return}
  const el=mode==='narrative'?$('#voice-text'):target;
  if(!el)return;
  const base=(el.type==='date'||el.tagName==='SELECT'||(el.dataset.field==='title'&&el.value==='Nova evidência'))?'':(el.value||'');
  const session={mode,el,base,committed:base,latest:base,cancelled:false,error:false,activityId:state.activity?.id};
  recognition=new Speech();speechContext=session;
  recognition.lang='pt-BR';recognition.continuous=true;recognition.interimResults=true;
  recognition.onstart=()=>{
    state.recording=true;
    if(mode==='narrative'){
      const status=$('#voice-status');if(status)status.textContent='● Ouvindo seu relato...';
      const button=document.querySelector('[data-act="voice"]');if(button)button.textContent='■ Parar e preencher campos';
    }else{
      document.querySelectorAll('.mic-button.listening').forEach(x=>x.classList.remove('listening'));
      session.trigger?.classList.add('listening');toast('Pode falar. Clique no microfone novamente quando terminar.');
    }
  };
  recognition.onresult=e=>{
    let intermediate='', allFinal='';
    for(let i=0;i<e.results.length;i++){
      const part=e.results[i][0].transcript;
      if(e.results[i].isFinal)allFinal+=' '+part;else intermediate+=' '+part;
    }
    const spoken=[allFinal,intermediate].join(' ').trim();
    session.latest=[session.base.trim(),spoken].filter(Boolean).join(' ').trim();
    if(el.type!=='date'&&el.tagName!=='SELECT')el.value=session.latest;
  };
  recognition.onerror=e=>{
    if(e.error==='aborted')return;
    session.error=true;
    const names={'not-allowed':'Permissão de microfone negada. Libere o microfone nas configurações do navegador.',
      'audio-capture':'Não foi possível encontrar um microfone.',
      'network':'O serviço de reconhecimento de fala está sem conexão.',
      'no-speech':'Nenhuma fala foi reconhecida.'};
    toast(names[e.error]||('Microfone: '+e.error),true);
  };
  recognition.onend=async()=>{
    if(speechContext!==session)return;
    state.recording=false;recognition=null;speechContext=null;
    document.querySelectorAll('.mic-button.listening').forEach(x=>x.classList.remove('listening'));
    const status=$('#voice-status');if(status)status.textContent='● Microfone parado';
    const button=document.querySelector('[data-act="voice"]');if(button)button.textContent='🎙 Falar e preencher tudo';
    const spoken=session.latest.slice(session.base.trim().length).trim();
    if(session.cancelled||session.error||!spoken)return;
    if(session.mode==='field'){
      updateDictatedField(session.el,session.latest);
    }else{
      state.voiceNarrative=session.latest;
      if(state.activity?.id!==session.activityId)return;
      await fillFromNarrative(session.latest);
    }
  };
  try{recognition.start()}catch(e){recognition=null;speechContext=null;toast(e.message,true)}
}
function toggleVoice(){startVoice('narrative')}
function voiceSingleField(button){
  if(recognition){stopVoice();return}
  const block=button.closest('.field,.photo-label');
  const target=block?.querySelector('[data-field],[data-group-field],[data-photo-field]');
  if(!target){toast('Campo não encontrado.',true);return}
  startVoice('field',target);
  if(speechContext)speechContext.trigger=button;
}
async function fillFromNarrative(text){
  if(state.voiceBusy)return;
  if(!state.activity)return;
  const activityId=state.activity.id;
  state.voiceBusy=true;
  try{
    const result=await api('/ai/interpret',{method:'POST',body:{text}});
    if(state.activity?.id!==activityId)return;
    let changed=0,conflicts=[];
    if(!result.fields?.activity_date&&/\bhoje\b/i.test(text)&&!state.activity.activity_date){
      const today=spokenDate('hoje');if(today){state.activity.activity_date=today;changed++}
    }
    for(const [key,value] of Object.entries(result.fields||{})){
      if(!fieldLabels[key]||!String(value||'').trim())continue;
      const old=String(state.activity[key]||'').trim();
      if(!old||(key==='title'&&['Nova evidência','Registro de atividade'].includes(old))){state.activity[key]=value;changed++}
      else if(old!==String(value).trim())conflicts.push(fieldLabels[key]);
    }
    if(result.project_name){
      const name=normalizeSpeech(result.project_name);
      const found=state.projects.find(p=>normalizeSpeech(p.name)===name);
      if(found&&!state.activity.project_id){state.activity.project_id=found.id;changed++}
    }
    for(const entry of result.groups||[]){
      const pos=Number(entry.position),g=state.activity.groups.find(x=>x.position===pos);
      if(!g)continue;
      for(const key of ['title','description','people']){
        const value=String(entry[key]||'').trim();if(value&&!String(g[key]||'').trim()){g[key]=value;changed++}
      }
    }
    if(changed){touch();await saveNow()}
    renderEditor();
    const area=$('#voice-text');if(area)area.value=state.voiceNarrative;
    const missing=(result.missing||[]).filter(Boolean);
    const report=`${changed} campo(s) preenchido(s) automaticamente.`+
      (conflicts.length?` Mantive dados existentes: ${conflicts.join(', ')}.`:'')+
      (missing.length?` Ainda faltam: ${missing.slice(0,5).join(', ')}.`:'')+
      (result.mode==='basic'?' Para extração mais completa, configure a chave de IA.':'');
    const display=$('#voice-fill-report');if(display)display.textContent=report;
    toast(report);
  }catch(e){toast('Não consegui interpretar o relato: '+e.message,true)}
  finally{state.voiceBusy=false}
}

async function listDocuments(){const docs=await api('/documents');state.activity=null;renderPage('Documentos gerados','Consulte versões anteriores em Word e PDF.',`<section class="panel"><div class="panel-head"><div><h3>Biblioteca de documentos</h3><p>${docs.length} arquivo(s) gerado(s).</p></div></div>${docs.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Evidência</th><th>Formato</th><th>Gerado em</th><th></th></tr></thead><tbody>${docs.map(x=>`<tr><td><b>${esc(x.activity_title)}</b></td><td><span class="pill">${esc(x.format.toUpperCase())}</span></td><td>${fmtTime(x.created_at)}</td><td><a class="btn small" href="/api/documents/${x.id}/download" download>↓ Baixar</a></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty-card"><h3>Nenhum documento gerado ainda.</h3><p>Aprove uma evidência para criar a primeira versão.</p></div>'}</section>`)}
async function listProjects(){const projects=await api('/projects');state.projects=projects;state.activity=null;renderPage('Projetos','Vincule as evidências às iniciativas que você acompanha.',`<section class="panel"><div class="panel-head"><h3>Projetos cadastrados <span class="pill">${projects.length}</span></h3><button class="btn primary" data-act="project-form">+ Adicionar projeto</button></div>${projects.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Projeto</th><th>Descrição</th><th></th></tr></thead><tbody>${projects.map(p=>`<tr><td><b>${esc(p.name)}</b></td><td>${esc(p.description||'Sem descrição')}</td><td><div class="table-actions"><button class="btn small" data-act="project-form" data-id="${p.id}">Editar</button><button class="btn small danger" data-act="delete-project" data-id="${p.id}">Excluir</button></div></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty-card"><h3>Nenhum projeto cadastrado</h3><button class="btn primary" data-act="project-form">Cadastrar projeto</button></div>'}</section>`)}
function projectForm(id){const p=state.projects.find(x=>x.id===id);modal(p?'Editar projeto':'Novo projeto',`<form id="project-form"><div class="field"><label>Nome do projeto</label><input name="name" required maxlength="250" value="${esc(p?.name||'')}" placeholder="Ex.: Incubadora Germinare"></div><div class="field"><label>Descrição</label><textarea name="description" rows="4" placeholder="Breve descrição do projeto">${esc(p?.description||'')}</textarea></div></form>`,`<button class="btn" data-act="close-modal">Cancelar</button><button class="btn primary" data-act="submit-project" data-id="${id||''}">Salvar projeto</button>`)}
async function submitProject(id){const f=$('#project-form');if(!f.reportValidity())return;const data=Object.fromEntries(new FormData(f));try{await api('/projects'+(id?'/'+id:''),{method:id?'PATCH':'POST',body:data});closeModal();await loadRefs();await listProjects();toast('Projeto salvo.')}catch(e){toast(e.message,true)}}
async function deleteProject(id){if(!confirm('Excluir projeto? As atividades serão mantidas, mas sem vínculo ao projeto.'))return;try{await api('/projects/'+id,{method:'DELETE'});await loadRefs();await listProjects();toast('Projeto excluído.')}catch(e){toast(e.message,true)}}
async function listPeople(){const people=await api('/people');state.people=people;state.activity=null;renderPage('Pessoas e componentes','Cadastre participantes e componentes usados nas atividades.',`<section class="panel"><div class="panel-head"><h3>Cadastro de pessoas</h3><button class="btn primary" data-act="person-form">+ Cadastrar pessoa</button></div>${people.length?`<div class="table-wrap"><table class="data-table"><thead><tr><th>Nome / componente</th><th>Tipo · função</th><th>Observações</th><th></th></tr></thead><tbody>${people.map(p=>`<tr><td><b>${esc(p.name)}</b></td><td>${p.kind==='component'?'Componente':'Pessoa'} · ${esc(p.role||'Não informado')}</td><td>${esc(p.notes||'')}</td><td><div class="table-actions"><button class="btn small" data-act="person-form" data-id="${p.id}">Editar</button><button class="btn small danger" data-act="delete-person" data-id="${p.id}">Excluir</button></div></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty-card"><h3>Nenhuma pessoa cadastrada</h3><p>Use o cadastro para consultar participantes recorrentes.</p></div>'}</section>`)}
function personForm(id){const p=state.people.find(x=>x.id===id);modal(p?'Editar cadastro':'Novo cadastro',`<form id="person-form"><div class="field"><label>Tipo</label><select name="kind"><option value="person" ${p?.kind!=='component'?'selected':''}>Pessoa</option><option value="component" ${p?.kind==='component'?'selected':''}>Componente</option></select></div><div class="field"><label>Nome</label><input name="name" required value="${esc(p?.name||'')}" maxlength="200"></div><div class="field"><label>Função ou papel</label><input name="role" value="${esc(p?.role||'')}"></div><div class="field"><label>Observações</label><textarea name="notes" rows="3">${esc(p?.notes||'')}</textarea></div></form>`,`<button class="btn" data-act="close-modal">Cancelar</button><button class="btn primary" data-act="submit-person" data-id="${id||''}">Salvar</button>`)}
async function submitPerson(id){const f=$('#person-form');if(!f.reportValidity())return;const data=Object.fromEntries(new FormData(f));try{await api('/people'+(id?'/'+id:''),{method:id?'PATCH':'POST',body:data});closeModal();await loadRefs();await listPeople();toast('Cadastro salvo.')}catch(e){toast(e.message,true)}}
async function deletePerson(id){if(!confirm('Excluir esta pessoa do cadastro?'))return;try{await api('/people/'+id,{method:'DELETE'});await listPeople();toast('Cadastro excluído.')}catch(e){toast(e.message,true)}}
async function listKnowledge(){const docs=await api('/knowledge');state.knowledge=docs;state.activity=null;renderPage('Base de conhecimento CERNE','Armazene referências verificadas para orientar a escrita das evidências.',`<div class="grid-2"><section class="panel"><div class="panel-head"><div><h3>Documentos de referência</h3><p>${docs.length} documento(s) indexado(s) para consulta.</p></div><button class="btn primary" data-act="knowledge-form">+ Nova referência</button></div>${docs.length?docs.map(d=>`<div class="knowledge-card"><div><div class="flex"><span class="pill ${d.verified?'green':'amber'}">${d.verified?'✓ Referência verificada':'Não verificada'}</span><span class="mini-tag">${d.chunks} trechos</span></div><h3>${esc(d.title)}</h3><p>${esc(d.content?.slice(0,240)||'')}</p><small>${esc(d.source||'Texto cadastrado')} · ${fmtTime(d.updated_at)}</small></div><div class="table-actions"><button class="btn small" data-act="knowledge-form" data-id="${d.id}">Editar</button><button class="btn small danger" data-act="delete-knowledge" data-id="${d.id}">×</button></div></div>`).join(''):'<div class="empty-card"><span class="icon">◎</span><h3>A base está vazia</h3><p>Adicione referências oficiais do CERNE para orientar os textos.</p></div>'}</section><div><section class="panel"><div class="panel-head"><h3>Importar documento</h3><span class="pill">PDF · DOCX · TXT</span></div><p class="helper-text">O sistema extrai o texto, separa em trechos e pesquisa passagens relevantes durante a revisão com IA.</p><form id="knowledge-upload-form"><div class="field"><label>Identificação do documento</label><input name="title" placeholder="Ex.: Manual CERNE, versão/edição..."></div><div class="field"><label>Arquivo de referência</label><input name="file" type="file" accept=".pdf,.docx,.txt,.md" required></div><div class="field"><label style="display:flex;align-items:center;gap:8px"><input type="checkbox" name="verified" value="true" style="width:auto;min-height:0"> Documento conferido com fonte oficial</label></div><button class="btn primary" type="submit">⇪ Importar e indexar</button></form><p class="note" style="margin-top:15px">PDF digitalizado sem texto selecionável precisa passar por OCR antes. O sistema não declara o documento como oficial automaticamente.</p></section><section class="panel"><h3>Como a IA utiliza o CERNE</h3><p class="helper-text">A plataforma recupera trechos relacionados à atividade e os apresenta com suas fontes. O texto deve distinguir informação comprovada, orientação institucional e lacunas de evidência.</p><div class="notice-box warn">Sem documentos confiáveis na base, não há como comprovar aderência a práticas específicas do CERNE. Cadastre primeiro as referências corretas.</div></section></div></div>`)}
function knowledgeForm(id){const d=state.knowledge.find(x=>x.id===id);modal(d?'Editar referência':'Adicionar referência',`<form id="knowledge-form"><div class="field"><label>Título</label><input name="title" value="${esc(d?.title||'')}" required maxlength="250"></div><div class="field"><label>Fonte ou versão</label><input name="source" value="${esc(d?.source||'')}" placeholder="Instituição, ano e versão"></div><div class="field"><label>Conteúdo textual</label><textarea name="content" rows="10" required minlength="10" maxlength="500000">${esc(d?.content||'')}</textarea></div><label class="flex" style="font-size:12px"><input type="checkbox" name="verified" value="true" ${d?.verified?'checked':''}> Conferido com a publicação de referência</label></form>`,`<button class="btn" data-act="close-modal">Cancelar</button><button class="btn primary" data-act="submit-knowledge" data-id="${id||''}">Salvar referência</button>`,true)}
async function submitKnowledge(id){const f=$('#knowledge-form');if(!f.reportValidity())return;const data=Object.fromEntries(new FormData(f));data.verified=!!f.elements.verified.checked;try{await api('/knowledge'+(id?'/'+id:''),{method:id?'PUT':'POST',body:data});closeModal();await listKnowledge();toast('Documento indexado para consulta.')}catch(e){toast(e.message,true)}}
async function uploadKnowledge(form){if(!form.reportValidity())return;try{const fd=new FormData(form);fd.set('verified',form.elements.verified.checked?'true':'false');const info=await api('/knowledge/upload',{method:'POST',body:fd});await listKnowledge();toast(`Documento importado com ${info.chunks} trecho(s) indexado(s).`)}catch(e){toast(e.message,true)}}
async function deleteKnowledge(id){if(!confirm('Excluir referência e seu índice de pesquisa?'))return;try{await api('/knowledge/'+id,{method:'DELETE'});await listKnowledge();toast('Referência excluída.')}catch(e){toast(e.message,true)}}
async function listTemplates(){const templates=await api('/templates');state.templates=templates;state.activity=null;renderPage('Modelos de documentos','Personalize a identidade visual dos documentos Word e PDF.',`<section class="panel"><div class="panel-head"><div><h3>Modelos disponíveis</h3><p>Configurações de cabeçalho, cores e rodapé.</p></div><div class="flex"><a class="btn" href="/api/templates/modelo-original/docx" download="Modelo_Original_Evidencia.docx">↓ Baixar modelo DOCX original</a><button class="btn primary" data-act="template-form">+ Novo modelo</button></div></div><div class="list-cards">${templates.map(t=>`<article class="evidence-card"><div style="height:8px;background:${esc(t.color)};border-radius:5px;margin-bottom:15px"></div><span class="mini-tag">MODELO WORD</span><h3>${esc(t.name)}</h3><p>${t.layout==='reference'?'Baseado no DOCX original enviado, com fotos e textos da atividade':esc(t.institution||t.subtitle)}</p><div class="details"><span>${esc(t.footer)}</span><button data-act="template-form" data-id="${t.id}">Editar →</button></div></article>`).join('')}</div></section>`)}
function templateForm(id){const t=state.templates.find(x=>x.id===id);modal(t?'Editar modelo':'Novo modelo',`<form id="template-form"><div class="field-row"><div class="field"><label>Nome do modelo</label><input name="name" required value="${esc(t?.name||'')}" maxlength="200"></div><div class="field"><label>Cor do título</label><input type="color" name="color" value="${esc(t?.color||'#125e78')}" style="height:46px;padding:5px"></div></div><div class="field"><label>Estrutura do documento</label><select name="layout"><option value="reference" ${(!t||t.layout==='reference')?'selected':''}>Modelo DOCX original enviado (título, fotos, participantes, objetivo, indicadores e competências)</option><option value="institutional" ${t?.layout==='institutional'?'selected':''}>Relatório institucional numerado (modelo antigo)</option></select></div><div class="field"><label>Título do documento</label><input name="subtitle" value="${esc(t?.subtitle||'RELATÓRIO DE EVIDÊNCIA')}"></div><div class="field"><label>Instituição no cabeçalho</label><input name="institution" value="${esc(t?.institution||'')}"></div><div class="field"><label>Rodapé</label><input name="footer" value="${esc(t?.footer||'Documento institucional')}"></div></form>`,`<button class="btn" data-act="close-modal">Cancelar</button><button class="btn primary" data-act="submit-template" data-id="${id||''}">Salvar modelo</button>`)}
async function submitTemplate(id){const f=$('#template-form');if(!f.reportValidity())return;const data=Object.fromEntries(new FormData(f));try{await api('/templates'+(id?'/'+id:''),{method:id?'PUT':'POST',body:data});closeModal();await loadRefs();await listTemplates();toast('Modelo salvo.')}catch(e){toast(e.message,true)}}
async function refreshAIState(){
  const u=await api('/auth/me');state.provider=u.provider;
  $('#provider-name').textContent=u.provider?`IA ${u.provider} configurada`:'Modo básico ativo';
  $('#provider-caption').textContent=u.provider?'Sugestões com IA e base CERNE':'Conecte uma chave para ativar IA';
  $('#provider-dot').classList.toggle('online',!!u.provider);
}
async function aiSettingsPage(){
  if(state.user?.role!=='admin'){toast('Apenas o administrador pode alterar a chave de IA.',true);await navigate('dashboard');return}
  const config=await api('/admin/ai');state.activity=null;
  renderPage('Configurações da IA','Cadastre sua chave aqui, sem precisar editar o arquivo .env.',
    `<section class="panel settings-panel"><div class="panel-head"><div><h3>Provedor de inteligência artificial</h3><p>Chave armazenada no servidor, protegida e nunca exibida por completo.</p></div><span class="pill ${config.configured?'green':'amber'}">${config.configured?'Chave cadastrada':'IA desativada'}</span></div>
    <form id="ai-settings-form" autocomplete="off"><div class="field"><label for="ai-provider">Serviço de IA</label><select name="provider" id="ai-provider"><option value="none" ${config.provider==='none'?'selected':''}>Desativada (revisão básica)</option><option value="gemini" ${config.provider==='gemini'?'selected':''}>Google Gemini</option><option value="openai" ${config.provider==='openai'?'selected':''}>OpenAI</option></select></div>
    <div class="field"><label for="ai-api-key">Chave da API</label><input type="password" id="ai-api-key" name="api_key" autocomplete="new-password" spellcheck="false" placeholder="Cole aqui sua chave privada" maxlength="1024"><small class="note">${config.configured?'Chave atual: '+esc(config.key_hint)+'. Deixe vazio para manter a chave cadastrada.':'A chave não será mostrada após salvar.'}</small></div>
    <div class="field"><label for="ai-model">Modelo</label><input id="ai-model" name="model" maxlength="120" spellcheck="false" value="${esc(config.model)}" placeholder="Ex.: gemini-2.5-flash"></div>
    <p class="note">A análise de textos envia o relato ao serviço escolhido. A análise de fotos exige confirmação. O consumo da API pode gerar cobrança no seu provedor.</p>
    <div class="settings-actions"><button type="submit" class="btn primary">Salvar configuração</button><button type="button" data-act="test-ai" class="btn">Testar conexão com IA</button></div>
    </form><p id="ai-settings-message" class="helper-text" role="status"></p></section>`);
}
async function saveAISettings(){
  const form=$('#ai-settings-form');if(!form.reportValidity())return;
  const payload=Object.fromEntries(new FormData(form));
  try{
    const result=await api('/admin/ai',{method:'PUT',body:payload});
    form.elements.api_key.value='';
    await refreshAIState();toast(result.configured?'Chave salva com segurança.':'IA desativada.');
    await aiSettingsPage();
  }catch(e){toast(e.message,true);$('#ai-settings-message').textContent=e.message}
}
async function testAISettings(){
  const out=$('#ai-settings-message');if(out)out.textContent='Verificando a conexão com o serviço...';
  try{const result=await api('/admin/ai/test',{method:'POST'});
    if(out)out.textContent=result.message;
    toast(result.message,!result.ok);
  }catch(e){if(out)out.textContent=e.message;toast(e.message,true)}
}
function accountModal(){setMenu(false);modal('Minha conta',`<p class="helper-text">${esc(state.user.email)}</p>${state.user.role==='admin'?'<p><a class="btn small" href="/api/admin/backup" download>↓ Baixar backup completo (registros, imagens e Word/PDF)</a></p><p class="note">Guarde o ZIP em local seguro. Ele contém dados pessoais e não inclui a senha ou chave de IA.</p>':''}<form id="password-form"><div class="field"><label>Senha atual</label><input type="password" name="old_password" autocomplete="current-password" required></div><div class="field"><label>Nova senha (mínimo 12 caracteres)</label><input type="password" name="new_password" minlength="12" autocomplete="new-password" required></div></form>`,`<button class="btn" data-act="logout">Sair</button><button class="btn primary" data-act="change-password">Alterar senha</button>`)}
async function changePassword(){const f=$('#password-form');if(!f.reportValidity())return;try{await api('/auth/password',{method:'POST',body:Object.fromEntries(new FormData(f))});closeModal();toast('Senha atualizada.')}catch(e){toast(e.message,true)}}
async function logout(){stopVoice(true);if(state.dirty||state.saving){try{await saveNow()}catch(e){toast(e.message,true);return}}try{await api('/auth/logout',{method:'POST'})}catch(e){if(state.user){toast('Não foi possível sair. '+e.message,true);return}}closeModal();state.activity=null;showLogin()}
// Single delegated event system keeps dynamic screens fully interactive.
document.addEventListener('click',async e=>{
  const target=e.target.closest('[data-act],[data-view]');
  if(!target)return;
  if(target.dataset.view){e.preventDefault();if(target.dataset.view==='editor')await newEvidence();else await navigate(target.dataset.view);return}
  const act=target.dataset.act, id=target.dataset.id;
  try{switch(act){case 'new':await newEvidence();break;case 'open':await navigate('editor',id);break;case 'search':await applyFilters();break;case 'ai-refine':await refineWithAI();break;case 'ai-photos':await describePhotos();break;case 'interpret':await interpretNarrative();break;case 'apply-ai':await applySuggestion();break;case 'close-modal':closeModal();break;case 'toggle-approval':await toggleApproval();break;case 'export':await exportDocument(target.dataset.format);break;case 'remove-photo':await moveOrDeletePhoto(id,'remove');break;case 'move-photo':await moveOrDeletePhoto(id,'move',target.dataset.direction);break;case 'history':await showHistory();break;case 'delete-activity':await deleteCurrent();break;case 'duplicate':await duplicateCurrent();break;case 'voice':toggleVoice();break;case 'voice-field':voiceSingleField(target);break;case 'test-ai':await testAISettings();break;case 'insert-person':{const name=$('#add-person-select')?.value;if(name){state.activity.participants=[state.activity.participants.trim(),name].filter(Boolean).join('; ');const el=$('#f-participants');if(el)el.value=state.activity.participants;touch();refreshPreview()}break}case 'project-form':projectForm(id);break;case 'submit-project':await submitProject(id);break;case 'delete-project':await deleteProject(id);break;case 'person-form':personForm(id);break;case 'submit-person':await submitPerson(id);break;case 'delete-person':await deletePerson(id);break;case 'knowledge-form':knowledgeForm(id);break;case 'submit-knowledge':await submitKnowledge(id);break;case 'delete-knowledge':await deleteKnowledge(id);break;case 'template-form':templateForm(id);break;case 'submit-template':await submitTemplate(id);break;case 'account':accountModal();break;case 'change-password':await changePassword();break;case 'logout':await logout();break;}}
  catch(err){toast(err.message,true)}
});
document.addEventListener('input',e=>{if(!state.activity||state.view!=='editor')return;const field=e.target.dataset.field,group=e.target.dataset.group,prop=e.target.dataset.groupField;if(field){state.activity[field]=e.target.value;touch();refreshPreview()}if(group&&prop){const g=state.activity.groups.find(x=>x.position===+group);if(g){g[prop]=e.target.value;touch();refreshPreview()}}});
document.addEventListener('change',async e=>{if(e.target.id==='ai-provider'){const model=$('#ai-model');if(model)model.value=({gemini:'gemini-2.5-flash',openai:'gpt-4o-mini',none:''})[e.target.value]||'';return}if(e.target.dataset.upload){await uploadPhotos(+e.target.dataset.upload,e.target.files)}if(e.target.dataset.photoField){try{const photoId=e.target.dataset.photoId;const property=e.target.dataset.photoField;const photo=state.activity?.groups.flatMap(g=>g.photos).find(p=>p.id===photoId);if(photo){await saveNow();const values={description:photo.description||'',people:photo.people||''};values[property]=e.target.value;const reply=await api('/photos/'+photoId,{method:'PATCH',body:values});Object.assign(photo,reply);const prior=state.activity.status;state.activity.status='draft';refreshPreview();if(prior==='approved'){const button=document.querySelector('[data-act="toggle-approval"]');if(button){button.textContent='✓ Aprovar evidência';button.classList.add('primary')}const badge=document.querySelector('.editor-headline .pill.green');if(badge)badge.outerHTML=statusBadge('draft');toast('A foto foi atualizada. Aprove novamente antes de exportar.')}else toast('Descrição da fotografia salva.')}}catch(err){toast(err.message,true)}}if(e.target.id==='template-selector'){state.currentTemplate=e.target.value;refreshPreview()}if(e.target.dataset.field){state.activity[e.target.dataset.field]=e.target.value;touch();refreshPreview()}});
document.addEventListener('submit',async e=>{if(e.target.id==='login-form'){e.preventDefault();$('#login-error').textContent='';const b=e.target.querySelector('button[type=submit]');b.disabled=true;try{const data=await api('/auth/login',{method:'POST',body:{email:$('#login-email').value,password:$('#login-password').value}});await loggedIn(data)}catch(err){$('#login-error').textContent=err.message}finally{b.disabled=false}}if(e.target.id==='ai-settings-form'){e.preventDefault();await saveAISettings()}if(e.target.id==='knowledge-upload-form'){e.preventDefault();await uploadKnowledge(e.target)}});
function setMenu(open){$('.sidebar').classList.toggle('open',open);$('#menu-backdrop').classList.toggle('hidden',!open);$('#mobile-menu').setAttribute('aria-expanded',String(open));$('#mobile-menu').setAttribute('aria-label',open?'Fechar menu':'Abrir menu')}
$('#mobile-menu').addEventListener('click',()=>setMenu(!$('.sidebar').classList.contains('open')));
$('#menu-backdrop').addEventListener('click',()=>setMenu(false));
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('.sidebar').classList.contains('open')){setMenu(false);$('#mobile-menu').focus()}});
window.addEventListener('resize',()=>{if(window.innerWidth>850)setMenu(false)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('.dialog-backdrop'))closeModal()});
window.addEventListener('beforeunload',e=>{if(state.dirty){e.preventDefault();e.returnValue=''}});
init();
