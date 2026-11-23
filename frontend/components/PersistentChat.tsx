"use client";
import {useCallback,useEffect,useMemo,useState} from "react";
import {AlertCircle,Bot,Loader2,MessageCircle,Plus,Send,Users,UserRound} from "lucide-react";
import {api} from "@/lib/api";
import type {TeamMember} from "@/lib/types";
import styles from "./PersistentChat.module.css";

type Scope="private"|"team";
type Conversation={id:string;kind:Scope;title:string;last_seq:number;last_message:string;last_message_at?:string|null;updated_at?:string|null;active?:boolean};
type Message={id:string;conversation_id:string;seq:number;sender_id:string|null;sender_name:string;role:"user"|"assistant";content:string;trigger_type?:string;created_at?:string|null;ai_status?:string|null;ai_error?:string|null};
type Props={scope:Scope;member:TeamMember|null;canEdit:boolean;onError:(message:string)=>void};
const timeLabel=(value?:string|null)=>{if(!value)return "";const d=new Date(value);return Number.isNaN(d.getTime())?"":d.toLocaleString("zh-CN",{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"});};

export default function PersistentChat({scope,member,canEdit,onError}:Props){
 const [items,setItems]=useState<Conversation[]>([]);
 const [selectedId,setSelectedId]=useState("");
 const [messages,setMessages]=useState<Message[]>([]);
 const [draft,setDraft]=useState("");
 const [busy,setBusy]=useState(false);
 const [creating,setCreating]=useState(false);
 const selected=items.find(x=>x.id===selectedId)||null;

 const loadItems=useCallback(async(keep=true)=>{
  try{const r=await api<{items:Conversation[]}>("chats?kind="+scope);setItems(r.items);if(!keep||!r.items.some(x=>x.id===selectedId))setSelectedId(r.items[0]?.id||"");}
  catch(e){onError(e instanceof Error?e.message:"会话列表加载失败");}
 },[scope,selectedId,onError]);
 const loadMessages=useCallback(async(id:string)=>{
  if(!id){setMessages([]);return;}
  try{const r=await api<{items:Message[]}>("chats/"+id+"/messages?after_seq=0&limit=200");setMessages(r.items);}
  catch(e){onError(e instanceof Error?e.message:"消息加载失败");}
 },[onError]);

 useEffect(()=>{setSelectedId("");setMessages([]);void loadItems(false);},[scope]);
 useEffect(()=>{if(selectedId)void loadMessages(selectedId);else setMessages([]);},[selectedId,loadMessages]);
 useEffect(()=>{if(!selectedId)return;const t=window.setInterval(()=>{void loadMessages(selectedId);void loadItems(true);},4000);return()=>window.clearInterval(t);},[selectedId,loadMessages,loadItems]);

 const ordered=useMemo(()=>[...messages].sort((a,b)=>a.seq-b.seq),[messages]);
 async function create(){
  if(!canEdit||creating)return;setCreating(true);onError("");
  try{const r=await api<Conversation>("chats",{method:"POST",body:JSON.stringify({kind:scope,title:scope==="private"?"新对话":"团队讨论"})});setItems(v=>[r,...v]);setSelectedId(r.id);setMessages([]);}
  catch(e){onError(e instanceof Error?e.message:"创建会话失败");}finally{setCreating(false);}
 }
 async function send(mention=false){
  const content=draft.trim();if(!selected||!content||!canEdit||busy)return;
  setBusy(true);onError("");setDraft("");
  try{
   const r=await api<{user_message:Message;assistant_message?:Message|null;ai_call?:{status:string;error?:string}|null}>("chats/"+selected.id+"/messages",{
    method:"POST",body:JSON.stringify({content,client_nonce:crypto.randomUUID(),trigger_ai:mention,trigger_type:mention?"mention":""})
   });
   setMessages(v=>[...v.filter(x=>x.id!==r.user_message.id),r.user_message,...(r.assistant_message?[r.assistant_message]:[])].sort((a,b)=>a.seq-b.seq));
   if(r.ai_call?.status==="failed")onError(r.ai_call.error||"AI 暂未返回，请检查模型配置。");
   void loadItems(true);
  }catch(e){setDraft(content);onError(e instanceof Error?e.message:"消息发送失败");}finally{setBusy(false);}
 }
 async function aiReply(){
  if(!selected||scope!=="team"||!canEdit||busy||!messages.length)return;
  setBusy(true);onError("");
  try{
   const r=await api<{assistant_message?:Message|null;ai_call?:{status:string;error?:string}|null}>("chats/"+selected.id+"/ai-replies",{method:"POST",body:JSON.stringify({idempotency_key:crypto.randomUUID()})});
   if(r.assistant_message)setMessages(v=>[...v,r.assistant_message!].sort((a,b)=>a.seq-b.seq));
   else if(r.ai_call?.status==="failed")onError(r.ai_call.error||"AI 回复失败，请检查模型配置。");
   void loadItems(true);
  }catch(e){onError(e instanceof Error?e.message:"AI 回复请求失败");}finally{setBusy(false);}
 }

 return <div className={styles.workspace}>
  <aside className={styles.list}>
   <div className={styles.listHeader}><div><small>{scope==="private"?"PRIVATE SPACE":"TEAM SPACE"}</small><h2>{scope==="private"?"私人会话":"团队会话"}</h2></div><button onClick={()=>void create()} disabled={!canEdit||creating} title="新建会话">{creating?<Loader2 size={16}/>:<Plus size={17}/>}</button></div>
   {items.length?items.map(x=><button key={x.id} className={styles.item+(selectedId===x.id?" "+styles.active:"")} onClick={()=>setSelectedId(x.id)}>
    <span className={styles.itemIcon}>{scope==="private"?<UserRound size={15}/>:<Users size={15}/>}</span>
    <span className={styles.itemText}><strong>{x.title}</strong><small>{x.last_message||"开始一段新的交流"}</small></span><time>{timeLabel(x.last_message_at||x.updated_at)}</time>
   </button>):<div className={styles.listEmpty}><MessageCircle size={22}/><p>还没有会话</p><button onClick={()=>void create()} disabled={!canEdit||creating}>创建第一个会话</button></div>}
   <div className={styles.listFoot}>{scope==="private"?"私人会话仅当前账号可见；消息会发送给已配置的模型服务。":"团队会话仅成员可见；普通消息只保存，不会自动调用 AI。"}</div>
  </aside>
  <section className={styles.panel}>
   {selected?<>
    <header className={styles.header}><div><small>{scope==="private"?"PRIVATE CONVERSATION":"SHARED TEAM CONVERSATION"}</small><h2>{selected.title}</h2><p>{scope==="private"?"私人消息默认调用模型。":"普通消息不触发模型；使用 @GPT 或 AI 回复显式调用。"}</p></div>
     {scope==="team"&&<button className={styles.aiButton} onClick={()=>void aiReply()} disabled={!canEdit||busy||!messages.length}><Bot size={15}/>AI 回复</button>}
    </header>
    <div className={styles.messages}>
     {ordered.length?ordered.map(m=><article key={m.id} className={styles.message+(m.role==="assistant"?" "+styles.assistant:" "+styles.user)}>
      <div className={styles.avatar}>{m.role==="assistant"?<Bot size={16>}/>:(m.sender_name||member?.name||"我").slice(0,1)}</div>
      <div className={styles.body}><div className={styles.meta}><strong>{m.role==="assistant"?"Research Atlas":m.sender_name||"成员"}</strong><time>{timeLabel(m.created_at)}</time>{m.trigger_type==="mention"&&<span>@GPT</span>}</div>
       <div className={styles.content}>{m.content}</div>{m.ai_status==="failed"&&<div className={styles.error}><AlertCircle size={13}/>{m.ai_error||"AI 回复失败"}</div>}
      </div>
     </article>):<div className={styles.empty}><MessageCircle size={26}/><h3>开始对话</h3><p>{scope==="private"?"直接输入研究问题或需要讨论的内容。":"发送普通消息；需要 AI 参与时使用 @GPT 发送或 AI 回复按钮。"}</p></div>}
     {busy&&<div className={styles.generating}><Loader2 size={16}/>正在处理消息…</div>}
    </div>
    <form className={styles.composer} onSubmit={e=>{e.preventDefault();void send(false);}}>
     <textarea value={draft} onChange={e=>setDraft(e.target.value)} rows={3} disabled={!canEdit||busy} placeholder={scope==="private"?"输入消息，Enter 发送，Shift + Enter 换行":"输入团队消息；需要 AI 时使用 @GPT 发送"}
      onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();void send(false);}}}/>
     <div className={styles.bottom}><span>{scope==="private"?"私人消息默认调用模型":"普通发送不调用模型"}</span><div>{scope==="team"&&<button type="button" className={styles.mention} onClick={()=>void send(true)} disabled={!canEdit||busy||!draft.trim()}>@GPT 发送</button>}<button type="submit" className={styles.send} disabled={!canEdit||busy||!draft.trim()}>{busy?<Loader2 size={15}/>:<Send size={15}/>}发送</button></div></div>
    </form>
   </>:<div className={styles.noChat}><MessageCircle size={30}/><h2>{scope==="private"?"私人对话":"团队对话"}</h2><p>创建会话后即可开始交流。消息与成员权限由 Research Atlas 管理。</p><button onClick={()=>void create()} disabled={!canEdit||creating}><Plus size={15}/>新建会话</button></div>}
  </section>
 </div>;
}
