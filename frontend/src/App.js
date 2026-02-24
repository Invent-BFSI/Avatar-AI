import { useState, useRef, useEffect, useCallback } from "react";
import * as SpeechSDK from "microsoft-cognitiveservices-speech-sdk";
import "./App.css";



const AVATARS = {
  lisa:  ["casual-sitting", "graceful-sitting", "graceful-standing", "technical-sitting", "technical-standing"],
  harry: ["business", "casual", "youthful"],
  jeff:  ["business"],
  lori:  ["casual"],
};

const VOICES = [
  { label: "Jenny — EN‑US",   value: "en-US-JennyNeural"    },
  { label: "Aria — EN‑US",    value: "en-US-AriaNeural"     },
  { label: "Guy — EN‑US",     value: "en-US-GuyNeural"      },
  { label: "Sonia — EN‑GB",   value: "en-GB-SoniaNeural"    },
  { label: "Natasha — EN‑AU", value: "en-AU-NatashaNeural"  },
  { label: "Xiaoxiao — ZH",   value: "zh-CN-XiaoxiaoNeural" },
  { label: "Keita — JA",      value: "ja-JP-KeitaNeural"    },
  { label: "Amala — DE",      value: "de-DE-AmalaNeural"    },
  { label: "Denise — FR",     value: "fr-FR-DeniseNeural"   },
];

const ts = () => new Date().toLocaleTimeString("en-GB", { hour12: false });

export default function App() {
  const [apiKey, setApiKey] = useState(
      process.env.REACT_APP_SPEECH_KEY || "" 
    );

  const [region, setRegion] = useState(
      process.env.REACT_APP_SPEECH_REGION || "eastus2"
    );
  const [char, setChar] = useState("lisa");
  const [style, setStyle] = useState("casual-sitting");
  const [voice, setVoice] = useState("en-US-JennyNeural");
  const [text, setText] = useState("Greetings. I am an Azure AI Avatar. How can I help you?");

  
  const [phase, setPhase] = useState("idle"); 
  const [logs, setLogs] = useState([{ t: ts(), m: "System Ready.", k: "sys" }]);

  const videoRef = useRef(null);
  const synthRef = useRef(null);
  const peerRef = useRef(null);
  const logBoxRef = useRef(null);
  const mattingCleanupRef = useRef(null);

  // Set the SDK reference immediately
  const sdkRef = useRef(SpeechSDK);

  useEffect(() => {
    if (logBoxRef.current) logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
  }, [logs]);

  useEffect(() => {
    setStyle(AVATARS[char][0]);
  }, [char]);

  const addLog = useCallback((m, k = "info") => {
    setLogs(prev => [...prev.slice(-80), { t: ts(), m, k }]);
  }, []);

// Inside App()
function startGreenScreenMatting(videoEl) {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  // We'll size once metadata is available (see onloadedmetadata below),
  // but set a reasonable default for safety:
  canvas.width = videoEl.videoWidth || 1280;
  canvas.height = videoEl.videoHeight || 720;

  videoEl.parentNode.insertBefore(canvas, videoEl);
  videoEl.style.display = "none";

  const keyColor = { r: 0, g: 255, b: 0 }; // #00FF00
  const threshold = 80; // adjust as needed

  let rafId = null;
  const frame = () => {
    if (videoEl.readyState >= 2) {
      // keep canvas in sync if stream size changes
      if (canvas.width !== videoEl.videoWidth && videoEl.videoWidth) {
        canvas.width = videoEl.videoWidth;
      }
      if (canvas.height !== videoEl.videoHeight && videoEl.videoHeight) {
        canvas.height = videoEl.videoHeight;
      }

      ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
      const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const d = img.data;
      for (let i = 0; i < d.length; i += 4) {
        const dr = d[i] - keyColor.r;
        const dg = d[i + 1] - keyColor.g;
        const db = d[i + 2] - keyColor.b;
        const dist = Math.sqrt(dr * dr + dg * dg + db * db);
        if (dist < threshold) d[i + 3] = 0; // make near-green pixels transparent
      }
      ctx.putImageData(img, 0, 0);
    }
    rafId = requestAnimationFrame(frame);
  };

  // kick things off
  rafId = requestAnimationFrame(frame);

  // return a disposer so we can stop the loop and restore the video if needed
  return () => {
    if (rafId) cancelAnimationFrame(rafId);
    // restore the original <video> element
    videoEl.style.display = "";
    if (canvas && canvas.parentNode) {
      canvas.parentNode.removeChild(canvas);
    }
  };
}

  
  const connect = async () => {
  if (!apiKey.trim()) { addLog("API key is required.", "err"); return; }
  setPhase("init");
  addLog("Initializing Azure Avatar...", "sys");

  try {
    const SDK = sdkRef.current;
    const speechConfig = SDK.SpeechConfig.fromSubscription(apiKey.trim(), region);
    speechConfig.speechSynthesisVoiceName = voice;

    // Video format & avatar config (your existing setup)
    const videoFormat = new SDK.AvatarVideoFormat();
    videoFormat.codec = "h264"; // or leave default; avoid SDP hacks
    const avatarConfig = new SDK.AvatarConfig(char, style, videoFormat);

    // For transparency via chroma-key green
    avatarConfig.backgroundColor = "#00FF00FF";

    // --- Peer connection ---
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    });
    peerRef.current = pc;

    // ✅ Add your ontrack handler here
    pc.ontrack = (e) => {
      if (e.track.kind === "video" && videoRef.current) {
        videoRef.current.srcObject = e.streams[0];

        const v = videoRef.current;
        const onMeta = () => {
          // In case there’s an existing matting loop, stop it
          if (mattingCleanupRef.current) {
            mattingCleanupRef.current();
            mattingCleanupRef.current = null;
          }
          // Start chroma-key matting and store the cleanup
          mattingCleanupRef.current = startGreenScreenMatting(v);
          v.removeEventListener("loadedmetadata", onMeta);
        };

        if (v.readyState >= 1) {
          onMeta(); // metadata already available
        } else {
          v.addEventListener("loadedmetadata", onMeta, { once: true });
        }
      }
    };

    // --- Synthesizer & connect (your existing code) ---
    const synthesizer = new SDK.AvatarSynthesizer(speechConfig, avatarConfig);
    synthRef.current = synthesizer;

    addLog("Negotiating handshake...", "sys");
    const result = await synthesizer.startAvatarAsync(pc);

    if (result.reason === SDK.ResultReason.SynthesizingAudioCompleted) {
      addLog("Avatar connected!", "ok");
      setPhase("live");
    } else {
      throw new Error(result.errorDetails || "Connection failed");
    }
  } catch (err) {
    addLog(`ERROR: ${err.message}`, "err");
    setPhase("error");
  }
};




  const speak = async () => {
    if (!synthRef.current || phase !== "live") return;
    setPhase("speaking");
    
    const ssml = `
    <speak version="1.0"
         xml:lang="en-US"
         xmlns="http://www.w3.org/2001/10/synthesis"
         xmlns:mstts="http://www.w3.org/2001/mstts"
         xmlns:emo="http://www.w3.org/2009/10/emotionml">
      <voice name="${voice}">
      ${text}
      </voice>
    </speak>`;

    try {
      await synthRef.current.speakSsmlAsync(ssml);
    } catch (e) {
      addLog(`Speak error: ${e.message}`, "err");
    } finally {
      setPhase("live");
    }
  };

  const disconnect = () => {
    synthRef.current?.close();
    peerRef.current?.close();
    setPhase("idle");
    addLog("Disconnected.");
  };
 const disconnect = () => {
  try {
    synthRef.current?.close();
    peerRef.current?.close();
  } finally {
    // stop the matting loop & restore the <video>
    if (mattingCleanupRef.current) {
      mattingCleanupRef.current();
      mattingCleanupRef.current = null;
    }
    // Also clear the video srcObject
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setPhase("idle");
    addLog("Disconnected.");
  }
};

  return (
    <div className="app-container">
      {/* Add your UI controls, inputs for API Key, and Video element here */}
      <video ref={videoRef} autoPlay playsInline style={{ width: '100%', maxWidth: '600px' }} />
      <button onClick={connect} disabled={phase !== "idle"}>Connect</button>
      <button onClick={speak} disabled={phase !== "live"}>Speak</button>
      <button onClick={() => askAgentAndSpeak(text)} disabled={phase !== "live"}>Ask Agent</button>
      <button onClick={disconnect}>Disconnect</button>
      <div className="log-box" ref={logBoxRef}>
        {logs.map((l, i) => <div key={i}>[{l.t}] {l.m}</div>)}
      </div>
    </div>
  );
}
