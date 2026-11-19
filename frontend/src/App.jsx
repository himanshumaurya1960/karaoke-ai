import { useState, useRef } from "react";
import "./App.css";
const API_URL = import.meta.env.VITE_API_URL;

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [message, setMessage] = useState("");
  const [stems, setStems] = useState(null);
  const [volumes, setVolumes] = useState({
    vocals: 0,
    drums: 100,
    bass: 100,
    other: 100,
  });
  const [mixFile, setMixFile] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [masterVolume, setMasterVolume] = useState(100);

  const audioContextRef = useRef(null);
  const audioSourcesRef = useRef({});
  const gainNodesRef = useRef({});
  const masterGainRef = useRef(null);
  const analyserRef = useRef(null);
  const [audioLevel, setAudioLevel] = useState(0);

  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const playbackStartTimeRef = useRef(null);
  const playbackOffsetRef = useRef(0);

  const handleFileChange = (event) => {
    const file = event.target.files[0];

    if (file) {
      setSelectedFile(file);
      setMessage("");
    }
  };

  const uploadSong = async () => {
    if (!selectedFile) {
      setMessage("Please select a song first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);

    setMessage("Uploading song...");

    try {
      const response = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed.");
      }

      setMessage("Song uploaded successfully!");
      console.log(data);
    } catch (error) {
      setMessage(`Error: ${error.message}`);
    }
  };

  const separateSong = async () => {
    // Prepare audio playback from the user's button click
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }

    await audioContextRef.current.resume();

    if (!selectedFile) {
      setMessage("Please upload a song first.");
      return;
    }

    setMessage("AI is separating vocals and instruments... Please wait.");

    try {
      const response = await fetch(
        `${API_URL}/separate?filename=${encodeURIComponent(
        selectedFile.name
      )}`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      console.log("Separation response:", data);

      if (!response.ok) {
        throw new Error(data.detail || "Separation failed.");
      }

      if (!data || !data.stems) {
        throw new Error("Backend did not return separated stems.");
      }

      setStems(data.stems);

      setMessage("Separation completed! Starting live mixer...");

      // Start live audio automatically
      await playLiveMixer(data.stems);

      setMessage(
        "Live mixer started! Adjust the sliders while the music plays."
      );
    } catch (error) {
      console.error("Separation error:", error);
      setMessage(`Error: ${error.message}`);
    }
  };

  const createMix = async () => {
    if (!selectedFile) {
      setMessage("Please select a song first.");
      return;
    }

    setMessage("Creating your custom mix...");

    try {
      const params = new URLSearchParams({
        filename: selectedFile.name,
        vocals: volumes.vocals,
        drums: volumes.drums,
        bass: volumes.bass,
        other: volumes.other,
      });

      const response = await fetch(
        `${API_URL}/mix?${params.toString()}`,
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Mixing failed.");
      }

      setMixFile(data.filename);

      setMessage("Custom mix created successfully!");

      console.log("Mix response:", data);
    } catch (error) {
      console.error("Mix error:", error);
      setMessage(`Error: ${error.message}`);
    }
  };

  const playLiveMixer = async (stemUrls) => {
    try {
      // Create AudioContext
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext();
      }

      await audioContextRef.current.resume();

      const audioContext = audioContextRef.current;

      const masterGain = audioContext.createGain();

      masterGain.gain.value = masterVolume / 100;

      const analyser = audioContext.createAnalyser();

      analyser.fftSize = 256;

      masterGain.connect(analyser);
      analyser.connect(audioContext.destination);

      analyserRef.current = analyser;

      const dataArray = new Uint8Array(
        analyser.frequencyBinCount
      );

      const updateMeter = () => {
        if (!analyserRef.current) {
          return;
        }

        analyser.getByteTimeDomainData(dataArray);

        let sum = 0;

        for (let i = 0; i < dataArray.length; i++) {
          const value = (dataArray[i] - 128) / 128;
          sum += value * value;
        }

        const rms = Math.sqrt(
          sum / dataArray.length
        );

        setAudioLevel(
          Math.min(100, Math.round(rms * 300))
        );

        requestAnimationFrame(updateMeter);
      };

      updateMeter();

      masterGainRef.current = masterGain;

      // Stop previous audio sources
      Object.values(audioSourcesRef.current).forEach((source) => {
        try {
          source.stop();
        } catch {}
      });

      audioSourcesRef.current = {};
      gainNodesRef.current = {};

      const stemNames = ["vocals", "drums", "bass", "other"];

      // Load all stems
      const buffers = {};

      for (const stem of stemNames) {

        const response = await fetch(`${API_URL}${stemUrls[stem]}`);
        if (!response.ok) {
          throw new Error(`Could not load ${stem} stem.`);
        }

        const arrayBuffer = await response.arrayBuffer();

        buffers[stem] = await audioContext.decodeAudioData(arrayBuffer);
      }

      // Start all stems together
      const startTime = audioContext.currentTime + 0.2;

      const playbackOffset = playbackOffsetRef.current;

      playbackStartTimeRef.current = startTime;

      if (buffers.vocals) {
        setDuration(buffers.vocals.duration);
      }

      stemNames.forEach((stem) => {
        const source = audioContext.createBufferSource();
        const gainNode = audioContext.createGain();

        source.buffer = buffers[stem];

        gainNode.gain.value = volumes[stem] / 100;

        source.connect(gainNode);
        gainNode.connect(masterGainRef.current);

        source.start(
          startTime,
          playbackOffset
        );

        audioSourcesRef.current[stem] = source;
        gainNodesRef.current[stem] = gainNode;
      });

      console.log("Live mixer started.");
      setIsPlaying(true);

      const updatePlaybackTime = () => {
        if (!playbackStartTimeRef.current) {
          return;
        }

        const elapsed =
          audioContext.currentTime -
          playbackStartTimeRef.current +
          playbackOffsetRef.current;

        if (elapsed >= 0) {
          setCurrentTime(
            Math.min(elapsed, duration || buffers.vocals.duration)
          );
        }

        if (
          audioSourcesRef.current.vocals &&
          elapsed < buffers.vocals.duration
        ) {
          requestAnimationFrame(updatePlaybackTime);
        }
      };

      requestAnimationFrame(updatePlaybackTime);
    } catch (error) {
      console.error("Live mixer error:", error);

      setMessage(`Live mixer error: ${error.message}`);
    }
  };

  const updateVolume = (stem, value) => {
    const newVolume = Number(value);

    setVolumes((previous) => ({
      ...previous,
      [stem]: newVolume,
    }));

    if (gainNodesRef.current[stem]) {
      gainNodesRef.current[stem].gain.value = newVolume / 100;
    }
  };

  const updateMasterVolume = (value) => {
    const newVolume = Number(value);

    setMasterVolume(newVolume);

    if (masterGainRef.current) {
      masterGainRef.current.gain.value = newVolume / 100;
    }
  };

  const stopLiveMixer = () => {
    Object.values(audioSourcesRef.current).forEach((source) => {
      try {
        source.stop();
      } catch {}
    });

    audioSourcesRef.current = {};

    playbackOffsetRef.current = 0;

    setCurrentTime(0);
    setIsPlaying(false);

    setMessage("Live mixer stopped.");
  };

  const seekLiveMixer = async (value) => {
    const newTime = Number(value);

    playbackOffsetRef.current = newTime;
    setCurrentTime(newTime);

    if (isPlaying && stems) {
      await playLiveMixer(stems);
    }
  };

  const resumeLiveMixer = async () => {
    if (!stems) {
      setMessage("Please separate a song first.");
      return;
    }

    await playLiveMixer(stems);

    setMessage(
      "Live mixer resumed. Adjust the sliders while the music plays."
    );
  };

  return (
    <div className="karaoke-app">
      <div className="container">
        <div className="header">
          <h1>🎵 Karaoke AI</h1>
          <p>Remove vocals and customize your music with AI.</p>
        </div>

        <div className="card">
          <h2>🎵 Choose Your Song</h2>

          <input
            className="file-input"
            type="file"
            accept=".mp3,.wav,.m4a,.flac,.ogg"
            onChange={handleFileChange}
          />

          {selectedFile && (
            <p className="selected-file">
              Selected song: <strong>{selectedFile.name}</strong>
            </p>
          )}

          <button onClick={uploadSong}>Upload Song</button>

          <button className="button-secondary" onClick={separateSong}>
            🤖 Separate Vocals & Instruments
          </button>
        </div>

        {stems && (
          <div className="card">
            <h2>🎚️ Live Stem Mixer</h2>

            <p className="mixer-description">
              Adjust each instrument while the music is playing.
            </p>

            <div className="stem master-volume">
              <div className="stem-header">
                <span className="stem-name">🔊 Master Volume</span>
                <span className="volume">{masterVolume}%</span>
              </div>

              <input
                type="range"
                min="0"
                max="200"
                value={masterVolume}
                onChange={(e) => updateMasterVolume(e.target.value)}
              />
            </div>

            <div className="live-status">
              {isPlaying
                ? "🟢 Live Mixer Playing"
                : "🔴 Live Mixer Stopped"}
            </div>

            <div className="playback-info">
              <span>
                {Math.floor(currentTime / 60)}:
                {String(Math.floor(currentTime % 60)).padStart(2, "0")}
              </span>

              <span>
                {Math.floor(duration / 60)}:
                {String(Math.floor(duration % 60)).padStart(2, "0")}
              </span>
            </div>

            <input
              className="playback-slider"
              type="range"
              min="0"
              max={duration || 0}
              step="0.1"
              value={currentTime}
              onChange={(e) =>
                seekLiveMixer(e.target.value)
              }
            />

            <div className="volume-meter">
              <div
                className="volume-meter-fill"
                style={{
                  width: `${audioLevel}%`,
                }}
              />
            </div>

            <div className="stem">
              <div className="stem-header">
                <span className="stem-name">🎤 Vocals</span>
                <span className="volume">{volumes.vocals}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="200"
                value={volumes.vocals}
                onChange={(e) => updateVolume("vocals", e.target.value)}
              />
            </div>

            <div className="stem">
              <div className="stem-header">
                <span className="stem-name">🥁 Drums</span>
                <span className="volume">{volumes.drums}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="200"
                value={volumes.drums}
                onChange={(e) => updateVolume("drums", e.target.value)}
              />
            </div>

            <div className="stem">
              <div className="stem-header">
                <span className="stem-name">🎸 Bass</span>
                <span className="volume">{volumes.bass}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="200"
                value={volumes.bass}
                onChange={(e) => updateVolume("bass", e.target.value)}
              />
            </div>

            <div className="stem">
              <div className="stem-header">
                <span className="stem-name">🎹 Other / Music</span>
                <span className="volume">{volumes.other}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="200"
                value={volumes.other}
                onChange={(e) => updateVolume("other", e.target.value)}
              />
            </div>

            <br />

            <button className="button-success" onClick={createMix}>
              🎚️ Create Custom Mix
            </button>

            <button className="button-secondary" onClick={stopLiveMixer}>
              ⏹️ Stop Live Mixer
            </button>

            <button className="button-secondary" onClick={resumeLiveMixer}>
              ▶️ Play Live Mixer
            </button>

            {mixFile && (
              <div className="download">
                <a
                  href={`${API_URL}/download/${encodeURIComponent(
                    mixFile
                  )}`}
                  download
                >
                  <button>⬇️ Download Custom Mix</button>
                </a>
              </div>
            )}
          </div>
        )}

        {message && <div className="status">{message}</div>}

        <footer className="footer">
          <p>🎵 Karaoke AI — AI-powered music customization</p>
        </footer>
      </div>
    </div>
  );
}

export default App;