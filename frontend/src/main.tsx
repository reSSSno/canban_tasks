import React, {useCallback, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {DndContext, useDraggable, useDroppable, type DragEndEvent} from '@dnd-kit/core';
import './style.css';

type Task={id:number;column_id:number;title:string;description:string;priority:string;due_date:string|null;assignee_id:number|null};
type Member={id:number;name:string;email:string;role:string};
type Board={role:string;columns:{id:number;name:string;tasks:Task[]}[];members:Member[]};
type Project={id:number;name:string;role:string};
const API='/api';
function App(){
 const [token,setToken]=useState(localStorage.getItem('token')||'');
 const [me,setMe]=useState(localStorage.getItem('name')||'');
 const [projects,setProjects]=useState<Project[]>([]);
 const [project,setProject]=useState<number|null>(null);
 const [board,setBoard]=useState<Board|null>(null);
 const [selected,setSelected]=useState<Task|null>(null);
 const [comments,setComments]=useState<{id:number;text:string;author:string}[]>([]);
 const [reports,setReports]=useState<{date:string;completed:number;total:number}[]>([]);
 const [error,setError]=useState('');
 const [register,setRegister]=useState(false);
 const [auth,setAuth]=useState({name:'',email:'',password:''});
 const [draft,setDraft]=useState({title:'',description:'',priority:'Обычный',due_date:'',assignee_id:''});
 const [comment,setComment]=useState('');
 const [member,setMember]=useState({email:'',role:'участник'});
 const request=useCallback(async(path:string,options:RequestInit={})=>{
  const response=await fetch(API+path,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{}),...options.headers}});
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Ошибка запроса');
  return data;
 },[token]);
 const action=async(fn:()=>Promise<unknown>)=>{try{setError('');await fn()}catch(e){setError((e as Error).message)}};
 const loadProjects=useCallback(async()=>setProjects(await request('/projects')),[request]);
 const loadBoard=useCallback(async(id:number)=>setBoard(await request('/projects/'+id+'/board')),[request]);
 useEffect(()=>{if(token)loadProjects().catch(e=>setError(e.message))},[token,loadProjects]);
 useEffect(()=>{if(project)loadBoard(project).catch(e=>setError(e.message))},[project,loadBoard]);
 useEffect(()=>{
  if(!project||!token)return;
  const protocol=location.protocol==='https:'?'wss':'ws';
  let active=true;let socket:WebSocket|undefined;let retry:number|undefined;
  function connect(){
   socket=new WebSocket(protocol+'://'+location.host+'/ws/projects/'+project+'?token='+encodeURIComponent(token));
   socket.onmessage=()=>{loadBoard(project!).catch(()=>{});if(selected)request('/tasks/'+selected.id+'/comments').then(setComments).catch(()=>{})};
   socket.onclose=()=>{if(active)retry=window.setTimeout(connect,2500)};
  }
  connect();return()=>{active=false;clearTimeout(retry);socket?.close()};
 },[project,token,loadBoard,request,selected?.id]);
 const authSubmit=async(e:React.FormEvent)=>{e.preventDefault();await action(async()=>{
  if(register){await request('/register',{method:'POST',body:JSON.stringify(auth)});setRegister(false);setError('Регистрация завершена. Войдите в систему.');return}
  const response=await request('/login',{method:'POST',body:JSON.stringify(auth)});
  localStorage.setItem('token',response.token);localStorage.setItem('name',response.name);setToken(response.token);setMe(response.name);
 })};
 const logout=()=>{localStorage.removeItem('token');localStorage.removeItem('name');setToken('');setBoard(null);setProject(null);setSelected(null)};
 const createProject=()=>action(async()=>{const name=prompt('Название нового проекта');if(!name?.trim())return;const p=await request('/projects',{method:'POST',body:JSON.stringify({name})});await loadProjects();setProject(p.id)});
 const createTask=(columnId:number)=>action(async()=>{const title=prompt('Название задачи');if(!title?.trim())return;await request('/columns/'+columnId+'/tasks',{method:'POST',body:JSON.stringify({title})});await loadBoard(project!)});
 const editTask=(id:number,changes:Record<string,unknown>)=>action(async()=>{await request('/tasks/'+id,{method:'PATCH',body:JSON.stringify(changes)});await loadBoard(project!);setSelected(s=>s?.id===id?{...s,...changes} as Task:s)});
 const openTask=(task:Task)=>{setSelected(task);setDraft({title:task.title,description:task.description,priority:task.priority,due_date:task.due_date||'',assignee_id:task.assignee_id?.toString()||''});action(async()=>setComments(await request('/tasks/'+task.id+'/comments')))};
 const onDragEnd=({active,over}:DragEndEvent)=>{if(!over||!board)return;const task=board.columns.flatMap(c=>c.tasks).find(t=>t.id===Number(active.id));const col=board.columns.find(c=>c.id===Number(over.id));if(task&&col&&task.column_id!==col.id)editTask(task.id,{column_id:col.id})};
 const isGuest=board?.role==='гость';
 if(!token)return <main className="auth"><section className="panel"><h1>Командная доска задач</h1><p>Планируйте работу вместе</p><form onSubmit={authSubmit}>{register&&<input required placeholder="Ваше имя" value={auth.name} onChange={e=>setAuth({...auth,name:e.target.value})}/>}<input required type="email" placeholder="Электронная почта" value={auth.email} onChange={e=>setAuth({...auth,email:e.target.value})}/><input required type="password" minLength={8} placeholder="Пароль (не менее 8 символов)" value={auth.password} onChange={e=>setAuth({...auth,password:e.target.value})}/><button>{register?'Зарегистрироваться':'Войти'}</button></form><button className="link" onClick={()=>setRegister(!register)}>{register?'Уже есть аккаунт? Войти':'Создать аккаунт'}</button>{error&&<p className="error">{error}</p>}</section></main>;
 return <div className="layout"><aside><h2>◈ Командная доска</h2><p className="muted">Пользователь: {me}</p><h3>Проекты</h3>{projects.map(p=><button key={p.id} className={'project '+(project===p.id?'active':'')} onClick={()=>{setProject(p.id);setSelected(null)}}>{p.name}<small>{p.role}</small></button>)}<button onClick={createProject}>+ Новый проект</button><button className="secondary logout" onClick={logout}>Выйти</button></aside><main className="workspace">{error&&<div className="error banner" onClick={()=>setError('')}>{error} ×</div>}{!project?<div className="welcome"><h1>Добро пожаловать!</h1><p>Выберите проект или создайте новый.</p></div>:board&&<><header><div><h1>{projects.find(p=>p.id===project)?.name}</h1><p className="muted">Ваша роль: {board.role}</p></div><div className="actions"><button className="secondary" onClick={()=>action(async()=>setReports(await request('/projects/'+project+'/reports')))}>Отчёты</button>{board.role==='владелец'&&<button className="secondary" onClick={()=>{const email=prompt('Email зарегистрированного пользователя');if(!email)return;const role=prompt('Роль: участник или гость','участник');if(role!=='участник'&&role!=='гость')return;setMember({email,role});action(async()=>{await request('/projects/'+project+'/members',{method:'POST',body:JSON.stringify({email,role})});await loadBoard(project)})}}>+ Участник</button>}{!isGuest&&<button onClick={()=>action(async()=>{const name=prompt('Название колонки');if(!name?.trim())return;await request('/projects/'+project+'/columns',{method:'POST',body:JSON.stringify({name})});await loadBoard(project)})}>+ Колонка</button>}</div></header><div className="people">Участники: {board.members.map(m=>m.name+' ('+m.role+')').join(', ')}</div><DndContext onDragEnd={onDragEnd}><div className="board">{board.columns.map(c=><ColumnView key={c.id} column={c} members={board.members} readOnly={isGuest} onOpen={openTask} onCreate={()=>createTask(c.id)}/>)}</div></DndContext>{reports.length>0&&<section className="reports"><h3>Еженедельные отчёты <button className="link" onClick={()=>setReports([])}>Закрыть</button></h3>{reports.map((r,i)=><p key={i}>{new Date(r.date).toLocaleDateString('ru-RU')}: выполнено за неделю {r.completed}, всего задач {r.total}</p>)}</section>}{selected&&<div className="overlay" onClick={()=>setSelected(null)}><section className="modal" onClick={e=>e.stopPropagation()}><div className="modalhead"><h2>Задача №{selected.id}</h2><button className="secondary" onClick={()=>setSelected(null)}>Закрыть</button></div><label>Название<input disabled={isGuest} value={draft.title} onChange={e=>setDraft({...draft,title:e.target.value})}/></label><label>Описание<textarea disabled={isGuest} value={draft.description} onChange={e=>setDraft({...draft,description:e.target.value})}/></label><label>Приоритет<select disabled={isGuest} value={draft.priority} onChange={e=>setDraft({...draft,priority:e.target.value})}>{['Низкий','Обычный','Высокий','Критический'].map(p=><option key={p}>{p}</option>)}</select></label><label>Срок<input disabled={isGuest} type="date" value={draft.due_date} onChange={e=>setDraft({...draft,due_date:e.target.value})}/></label><label>Исполнитель<select disabled={isGuest} value={draft.assignee_id} onChange={e=>setDraft({...draft,assignee_id:e.target.value})}><option value="">Не назначен</option>{board.members.filter(m=>m.role!=='гость').map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>{!isGuest&&<div className="actions"><button onClick={()=>editTask(selected.id,{title:draft.title,description:draft.description,priority:draft.priority,due_date:draft.due_date||null,assignee_id:draft.assignee_id?Number(draft.assignee_id):null})}>Сохранить</button><button className="danger" onClick={()=>{if(confirm('Удалить задачу?'))action(async()=>{await request('/tasks/'+selected.id,{method:'DELETE'});setSelected(null);await loadBoard(project)})}}>Удалить</button></div>}<h3>Комментарии</h3><div className="comments">{comments.map(c=><div className="comment" key={c.id}><b>{c.author}</b><p>{c.text}</p></div>)}</div>{!isGuest&&<form onSubmit={e=>{e.preventDefault();action(async()=>{await request('/tasks/'+selected.id+'/comments',{method:'POST',body:JSON.stringify({text:comment})});setComment('');setComments(await request('/tasks/'+selected.id+'/comments'))})}}><textarea required placeholder="Напишите комментарий" value={comment} onChange={e=>setComment(e.target.value)}/><button>Отправить</button></form>}</section></div>}</>}</main></div>
}
function ColumnView({column,members,readOnly,onOpen,onCreate}:{column:Board['columns'][number];members:Member[];readOnly:boolean;onOpen:(t:Task)=>void;onCreate:()=>void}){
 const {setNodeRef,isOver}=useDroppable({id:column.id});
 return <section className={'column '+(isOver?'over':'')} ref={setNodeRef}><div className="columnhead"><h3>{column.name}</h3><span>{column.tasks.length}</span></div>{column.tasks.map(t=><TaskCard key={t.id} task={t} members={members} readOnly={readOnly} onOpen={()=>onOpen(t)}/>)}{!readOnly&&<button className="addtask" onClick={onCreate}>+ Добавить задачу</button>}</section>
}
function TaskCard({task,members,readOnly,onOpen}:{task:Task;members:Member[];readOnly:boolean;onOpen:()=>void}){
 const {attributes,listeners,setNodeRef,transform,isDragging}=useDraggable({id:task.id,disabled:readOnly});
 return <article ref={setNodeRef} className={'task '+(isDragging?'dragging':'')} style={{transform:transform?`translate3d(${transform.x}px,${transform.y}px,0)`:undefined}}><div className="tasktop"><span className="priority">{task.priority}</span>{!readOnly&&<span className="handle" {...listeners} {...attributes} aria-label="Перетащить задачу">⠿</span>}</div><button className="tasktitle" onClick={onOpen}>{task.title}</button><p>{task.description.slice(0,90)}</p><div className="taskfoot"><span>{members.find(m=>m.id===task.assignee_id)?.name||'Без исполнителя'}</span><span>{task.due_date||''}</span></div></article>
}
createRoot(document.getElementById('root')!).render(<App/>);
