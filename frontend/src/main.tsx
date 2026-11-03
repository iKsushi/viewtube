import React from 'react';
import ReactDOM from 'react-dom/client';
import {BrowserRouter,Link,Route,Routes} from 'react-router-dom';
import {AuthProvider} from './state';
import Layout from './components/Layout';
import {Empty} from './components/UI';
import Feed from './pages/Feed';
import Auth from './pages/Auth';
import Watch from './pages/Watch';
import Upload from './pages/Upload';
import Studio from './pages/Studio';
import Channel from './pages/Channel';
import Playlists,{PlaylistDetail} from './pages/Playlists';
import Moderation,{Admin} from './pages/Moderation';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><AuthProvider><Routes><Route element={<Layout/>}><Route index element={<Feed/>}/><Route path="explore" element={<Feed key="popular" scope="popular"/>}/><Route path="search" element={<Feed key="search"/>}/>{['subscriptions','history','liked','shared'].map(scope=><Route path={scope} key={scope} element={<Feed key={scope} scope={scope}/>}/>)}<Route path="login" element={<Auth key="login"/>}/><Route path="register" element={<Auth key="register" register/>}/><Route path="watch/:id" element={<Watch/>}/><Route path="upload" element={<Upload/>}/><Route path="studio" element={<Studio/>}/><Route path="channel/:id" element={<Channel/>}/><Route path="playlists" element={<Playlists/>}/><Route path="playlist/:id" element={<PlaylistDetail/>}/><Route path="moderation" element={<Moderation/>}/><Route path="admin" element={<Admin/>}/><Route path="*" element={<Empty title="Страница не найдена" description="Возможно, ссылка устарела."><Link to="/" className="button primary">На главную</Link></Empty>}/></Route></Routes></AuthProvider></BrowserRouter></React.StrictMode>);
