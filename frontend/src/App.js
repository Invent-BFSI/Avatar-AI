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

  const connect = async () => {
  if (!apiKey.trim()) { addLog("API key is required.", "err"); return; }
  setPhase("init");
  addLog("Initializing Azure Avatar with VP9 transparency...", "sys");

  try {
    const SDK = sdkRef.current;
    const speechConfig = SDK.SpeechConfig.fromSubscription(apiKey.trim(), region);
    speechConfig.speechSynthesisVoiceName = voice;

    // 1. Configure Video Format for VP9
    const videoFormat = new SDK.AvatarVideoFormat();
    // Explicitly set the codec to vp9 in the config object
    videoFormat.codec = "vp9"; 
    
    const avatarConfig = new SDK.AvatarConfig(char, style, videoFormat);
    avatarConfig.backgroundColor = "#000000"; // Transparent

    // 2. Setup Peer Connection
    const pc = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }] 
    });
    peerRef.current = pc;

    // 3. FORCE VP9 via SDP Manipulation
    // This is the critical fix for Error 1007
    const originalCreateOffer = pc.createOffer.bind(pc);
    pc.createOffer = async (options) => {
      const offer = await originalCreateOffer(options);
      // Moves VP9 to the front of the codec list in the SDP string
      offer.sdp = offer.sdp.replace(/m=video (.*) SAVPF (.*)/g, (match, p1, p2) => {
        const codecs = p2.split(' ');
        // 96 is a common dynamic payload type for VP9 in browsers
        return `m=video ${p1} SAVPF 96 ${codecs.filter(c => c !== '96').join(' ')}`;
      });
      return offer;
    };

    pc.ontrack = (e) => {
      if (e.track.kind === "video" && videoRef.current) {
        videoRef.current.srcObject = e.streams[0];
      }
    };

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
    
    const ssml = `<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
      <voice name="${voice}">${text}</voice>
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

  return (
    <div className="app-container">
      {/* Add your UI controls, inputs for API Key, and Video element here */}
      <video ref={videoRef} autoPlay playsInline style={{ width: '100%', maxWidth: '600px' }} />
      <button onClick={connect} disabled={phase !== "idle"}>Connect</button>
      <button onClick={speak} disabled={phase !== "live"}>Speak</button>
      <button onClick={disconnect}>Disconnect</button>
      <div className="log-box" ref={logBoxRef}>
        {logs.map((l, i) => <div key={i}>[{l.t}] {l.m}</div>)}
      </div>
    </div>
  );
}
