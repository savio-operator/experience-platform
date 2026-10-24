"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <main id="main" style={{ maxWidth: 680, margin: "64px auto", padding: 24 }}><h1>That didn’t quite work.</h1><p>No real booking or payment was made. Try loading this demo screen again.</p><button onClick={reset}>Retry</button></main>;
}
