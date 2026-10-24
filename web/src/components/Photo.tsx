"use client";

import Image from "next/image";
import { useState } from "react";
import { photos, type PhotoId } from "@/lib/fixtures";
import s from "./photo.module.css";

export default function Photo({ id, sizes = "(max-width: 700px) 100vw, 50vw", eager = false }: { id: PhotoId; sizes?: string; eager?: boolean }) {
  const [failed, setFailed] = useState(false);
  const photo = photos[id];
  return <div className={s.frame}>
    {failed ? <span className={s.fallback}>Photo unavailable</span> : <Image src={photo.src} alt={photo.alt} fill sizes={sizes} loading={eager ? "eager" : "lazy"} style={{ objectFit: "cover", objectPosition: photo.position }} onError={() => setFailed(true)} />}
  </div>;
}
