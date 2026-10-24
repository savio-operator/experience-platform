"use client";

import { useState } from "react";
import { useDemo } from "./DemoProvider";
import { conversationTitle, hasContent } from "@/lib/chat-history";
import s from "./history.module.css";

export default function ChatHistory({ onNavigate }: { onNavigate: () => void }) {
  const demo = useDemo();
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const chats = demo.conversations.filter(item => hasContent(item) && `${conversationTitle(item)} ${item.chat.messages.map(message => message.text).join(" ")}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

  return <aside className={s.sidebar} aria-label="Chat history">
    <div className={s.heading}><h2>Your conversations</h2><span>{demo.conversations.filter(hasContent).length}</span></div>
    <button className={s.newChat} disabled={!demo.ready} onClick={() => { demo.newChat(); onNavigate(); }}><span aria-hidden="true">＋</span> New conversation</button>
    <label className={s.search}><span className={s.srOnly}>Search chat history</span><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search your chats" /></label>
    <div className={s.list}>
      {!demo.ready ? <p className={s.empty} role="status">Opening your history…</p> : !chats.length ? <p className={s.empty}>{search ? "No conversations match that search." : "Your conversations will appear here. Start with whatever’s on your mind."}</p> : chats.map(chat => <div className={s.row} key={chat.id} data-active={chat.id === demo.activeId}>
        <button className={s.open} aria-current={chat.id === demo.activeId ? "true" : undefined} onClick={() => { demo.openChat(chat.id); setDeleting(null); onNavigate(); }}>
          <strong>{conversationTitle(chat)}</strong><span>{new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }).format(new Date(chat.updatedAt))}{!chat.chat.messages.length ? " · Draft" : ""}</span>
        </button>
        <button className={s.delete} aria-label={`Delete ${conversationTitle(chat)}`} onClick={() => setDeleting(chat.id)}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7"/></svg></button>
        {deleting === chat.id && <div className={s.confirm} role="group" aria-label="Delete conversation"><p>Delete this chat from this browser? This can’t be undone.</p><div><button onClick={() => setDeleting(null)}>Keep chat</button><button onClick={() => { demo.deleteChat(chat.id); setDeleting(null); }}>Delete chat</button></div></div>}
      </div>)}
    </div>
    <p className={s.storageNote}>Saved on this browser.<br />Not synced to a cloud account. Anyone using this browser can reopen these chats.</p>
  </aside>;
}
