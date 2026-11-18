import React from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import type { Board, Member, Task } from '../types';

export function ColumnView({column,members,readOnly,onOpen,onCreate}:{column:Board['columns'][number];members:Member[];readOnly:boolean;onOpen:(t:Task)=>void;onCreate:()=>void}){
 const {setNodeRef,isOver}=useDroppable({id:column.id});
 return <section className={'column '+(isOver?'over':'')} ref={setNodeRef}><div className="columnhead"><h3>{column.name}</h3><span>{column.tasks.length}</span></div>{column.tasks.map(t=><TaskCard key={t.id} task={t} members={members} readOnly={readOnly} onOpen={()=>onOpen(t)}/>)}{!readOnly&&<button className="addtask" onClick={onCreate}>+ Добавить задачу</button>}</section>
}
export function TaskCard({task,members,readOnly,onOpen}:{task:Task;members:Member[];readOnly:boolean;onOpen:()=>void}){
 const {attributes,listeners,setNodeRef,transform,isDragging}=useDraggable({id:task.id,disabled:readOnly});
 return <article ref={setNodeRef} className={'task '+(isDragging?'dragging':'')} style={{transform:transform?`translate3d(${transform.x}px,${transform.y}px,0)`:undefined}}><div className="tasktop"><span className="priority">{task.priority}</span>{!readOnly&&<span className="handle" {...listeners} {...attributes} aria-label="Перетащить задачу">⠿</span>}</div><button className="tasktitle" onClick={onOpen}>{task.title}</button><p>{task.description.slice(0,90)}</p><div className="taskfoot"><span>{members.find(m=>m.id===task.assignee_id)?.name||'Без исполнителя'}</span><span>{task.due_date||''}</span></div></article>
}
