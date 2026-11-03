import {useEffect,useRef,useState,type ReactNode} from 'react';
import {Link} from 'react-router-dom';
import {AlertCircle,Check,Film,LoaderCircle,X} from 'lucide-react';
import {ago,duration,number,type Video} from '../types';

export function Avatar({name,color='#7765be',large=false}:{name:string;color?:string;large?:boolean}){return <span className={`avatar ${large?'large':''}`} style={{background:color}} aria-hidden="true">{name.slice(0,1).toUpperCase()}</span>;}
export function Spinner(){return <div className="loading" role="status"><LoaderCircle className="spin" size={24}/><span>Загружаем…</span></div>;}
export function ErrorBox({message,retry}:{message:string;retry?:()=>void}){return <div className="error-box" role="alert"><AlertCircle size={20}/><span>{message}</span>{retry&&<button className="text-button" onClick={retry}>Попробовать снова</button>}</div>;}
export function Empty({title,description,children}:{title:string;description:string;children?:ReactNode}){return <div className="empty"><span className="empty-icon"><Film size={34}/></span><h2>{title}</h2><p>{description}</p>{children}</div>;}
export function LoginRequired(){return <Empty title="Здесь будет ваша коллекция" description="Войдите, чтобы сохранять видео, подписываться на авторов и продолжать просмотр."><Link className="button primary" to="/login">Войти</Link></Empty>;}
export function VideoCard({video,compact=false}:{video:Video;compact?:boolean}){
  return <article className={`video-card ${compact?'compact':''}`}><Link className="thumbnail" to={`/watch/${video.id}`} aria-label={`Смотреть: ${video.title}`}>
    {video.thumbnail?<img src={video.thumbnail} alt="" loading="lazy"/>:<div className="thumb-fallback"><Film size={40}/></div>}<span className="duration">{duration(video.duration)}</span>
    {video.position>0&&<span className="watch-progress" style={{width:`${Math.min(100,video.position/Math.max(1,video.duration)*100)}%`}}/>}
  </Link><div className="video-info">{!compact&&<Link to={`/channel/${video.channel.id}`} aria-label={`Канал ${video.channel.name}`}><Avatar name={video.channel.name} color={video.channel.color}/></Link>}
    <div><Link className="video-title" to={`/watch/${video.id}`}>{video.title}</Link><Link className="video-author" to={`/channel/${video.channel.id}`}>{video.channel.name}</Link><p className="video-meta">{number(video.views)} просмотров <span>•</span> {ago(video.created_at)}</p></div></div></article>;
}
export function VideoGrid({videos}:{videos:Video[]}){return <div className="video-grid">{videos.map(v=><VideoCard key={v.id} video={v}/>)}</div>;}
export function Modal({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}){
  const ref=useRef<HTMLDialogElement>(null), close=useRef(onClose);close.current=onClose;
  useEffect(()=>{const node=ref.current;node?.showModal();const onCancel=(e:Event)=>{e.preventDefault();close.current();};node?.addEventListener('cancel',onCancel);return()=>{node?.removeEventListener('cancel',onCancel);node?.close();};},[]);
  return <dialog ref={ref} className="modal" aria-label={title} onClick={e=>{if(e.target===ref.current)onClose();}}><div className="modal-header"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Закрыть"><X/></button></div>{children}</dialog>;
}
export function CopyButton({value,label='Копировать ссылку'}:{value:string;label?:string}){const [copied,setCopied]=useState(false),[error,setError]=useState('');return <><button className="button secondary" onClick={async()=>{try{await navigator.clipboard.writeText(value);setCopied(true);}catch{setError('Копирование недоступно. Выделите и скопируйте ссылку вручную.');}}}>{copied?<><Check size={17}/>Скопировано</>:label}</button>{error&&<p role="status">{error}</p>}</>;}
