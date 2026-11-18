import React, { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/Header';
import MapViewer from './components/MapViewer';
import ChannelSelector from './components/ChannelSelector';
import ColorLegend from './components/ColorLegend';
import TimelineBar from './components/TimelineBar';
import InfoModal from './components/InfoModal';
import { 
  DEFAULT_CHANNELS,
  fetchBounds, 
  fetchChannels, 
  fetchFrames, 
  fetchLegend, 
  fetchHealth 
} from './services/apiClient';

export default function App() {
  // Application State - Pre-populated with default ABI channels
  const [channels, setChannels] = useState(DEFAULT_CHANNELS);
  const [currentChannel, setCurrentChannel] = useState('C13');
  const [frameCount, setFrameCount] = useState(24);
  const [frames, setFrames] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [fps, setFps] = useState(8);
  const [opacity, setOpacity] = useState(0.85);
  const [basemap, setBasemap] = useState('dark');
  const [showBorders, setShowBorders] = useState(true);
  const [boundsMeta, setBoundsMeta] = useState(null);
  const [legend, setLegend] = useState(null);
  const [apiOnline, setApiOnline] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [preloadedCount, setPreloadedCount] = useState(0);
  const [coords, setCoords] = useState({ lat: null, lon: null });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const [autoSync, setAutoSync] = useState(true);

  // Animation timing refs
  const animationFrameRef = useRef(null);
  const lastTickTimeRef = useRef(0);
  const isPlayingRef = useRef(isPlaying);
  isPlayingRef.current = isPlaying;
  const fpsRef = useRef(fps);
  fpsRef.current = fps;
  const totalFramesRef = useRef(frames.length);
  totalFramesRef.current = frames.length;

  // 1. Initial Load: Check Health, Bounds, and Channels
  useEffect(() => {
    async function initSystem() {
      try {
        await fetchHealth();
        setApiOnline(true);
      } catch (err) {
        console.warn('API health check failed:', err);
        setApiOnline(false);
      }

      try {
        const bounds = await fetchBounds();
        setBoundsMeta(bounds);
      } catch (err) {
        console.error('Error fetching bounds:', err);
      }

      try {
        const chList = await fetchChannels();
        setChannels(chList);
      } catch (err) {
        console.error('Error fetching channels:', err);
      }
    }
    initSystem();
  }, []);

  // 2. Fetch Frames when Channel or FrameCount changes
  useEffect(() => {
    let isCancelled = false;

    async function loadChannelFrames() {
      setIsLoading(true);
      setPreloadedCount(0);
      try {
        const data = await fetchFrames(currentChannel, frameCount);
        if (!isCancelled) {
          const loadedFrames = data.frames || [];
          setFrames(loadedFrames);
          // Default to latest frame (end of array)
          setCurrentIndex(loadedFrames.length > 0 ? loadedFrames.length - 1 : 0);
        }
      } catch (err) {
        if (!isCancelled) {
          console.error(`Error loading frames for ${currentChannel}:`, err);
          setFrames([]);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    loadChannelFrames();

    // Fetch calibrated color legend for channel
    async function loadChannelLegend() {
      try {
        const leg = await fetchLegend(currentChannel);
        if (!isCancelled) {
          setLegend(leg);
        }
      } catch (err) {
        console.warn('Error fetching legend:', err);
      }
    }

    loadChannelLegend();

    return () => {
      isCancelled = true;
    };
  }, [currentChannel, frameCount]);

  // 3. Background Auto-Sync: Polls for new satellite frames every 30 seconds
  useEffect(() => {
    if (!autoSync) return;

    const syncTimer = setInterval(async () => {
      try {
        const data = await fetchFrames(currentChannel, frameCount);
        if (data?.frames && data.frames.length > 0) {
          setFrames((prevFrames) => {
            const prevLastTs = prevFrames.length > 0 ? prevFrames[prevFrames.length - 1].timestamp : null;
            const newLastTs = data.frames[data.frames.length - 1].timestamp;

            if (newLastTs && newLastTs !== prevLastTs) {
              console.log(`[Auto-Sync] New observation detected: ${newLastTs} (${currentChannel})`);

              // If currently parked at latest, advance to new latest
              setCurrentIndex((prevIdx) => {
                if (prevIdx >= prevFrames.length - 1) {
                  return data.frames.length - 1;
                }
                return prevIdx;
              });

              return data.frames;
            }
            return prevFrames;
          });
        }
      } catch (err) {
        // Silently skip background poll failure
      }
    }, 30000); // 30s auto-refresh check

    return () => clearInterval(syncTimer);
  }, [currentChannel, frameCount, autoSync]);

  // 3. Smooth Delta-timed Animation Loop
  const animate = useCallback((now) => {
    if (!isPlayingRef.current) return;

    const interval = 1000 / fpsRef.current;
    if (now - lastTickTimeRef.current >= interval) {
      lastTickTimeRef.current = now;
      setCurrentIndex((prev) => {
        const total = totalFramesRef.current;
        if (total <= 1) return 0;
        return (prev + 1) % total;
      });
    }

    animationFrameRef.current = requestAnimationFrame(animate);
  }, []);

  useEffect(() => {
    if (isPlaying) {
      lastTickTimeRef.current = performance.now();
      animationFrameRef.current = requestAnimationFrame(animate);
    } else if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, animate]);

  // 4. Keyboard Shortcuts: Space (Play/Pause), Left/Right (Step)
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't intercept if inside an input or modal
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;

      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((prev) => !prev);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        setIsPlaying(false);
        setCurrentIndex((prev) => (frames.length > 0 ? (prev + 1) % frames.length : 0));
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        setIsPlaying(false);
        setCurrentIndex((prev) => (frames.length > 0 ? (prev - 1 + frames.length) % frames.length : 0));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [frames.length]);

  // Step handlers for UI buttons
  const handleStepBack = () => {
    setIsPlaying(false);
    setCurrentIndex((prev) => (frames.length > 0 ? (prev - 1 + frames.length) % frames.length : 0));
  };

  const handleStepForward = () => {
    setIsPlaying(false);
    setCurrentIndex((prev) => (frames.length > 0 ? (prev + 1) % frames.length : 0));
  };

  const currentChannelMeta = channels.find((c) => c.channel === currentChannel) || null;
  const currentFrame = frames[currentIndex] || null;

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#0B0F19]">
      {/* Top Header */}
      <Header
        channels={channels}
        currentChannel={currentChannel}
        onSelectChannel={setCurrentChannel}
        channelMeta={currentChannelMeta}
        coords={coords}
        currentFrame={currentFrame}
        apiOnline={apiOnline}
        autoSync={autoSync}
        onToggleAutoSync={() => setAutoSync((prev) => !prev)}
        onOpenInfo={() => setInfoOpen(true)}
        onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
        sidebarOpen={sidebarOpen}
      />

      {/* Main Map Workstation */}
      <div className="relative flex-1 w-full h-full overflow-hidden">
        {/* Leaflet Map with Double-Buffering */}
        <MapViewer
          boundsMeta={boundsMeta}
          frames={frames}
          currentIndex={currentIndex}
          opacity={opacity}
          basemap={basemap}
          showBorders={showBorders}
          onMouseMove={setCoords}
          onPreloadProgress={setPreloadedCount}
        />

        {/* Floating Quick Map Controls (Opacity, Borders & Basemap) */}
        <div className="absolute top-20 left-3 z-[1000] bg-slate-900/95 border border-slate-800 rounded-2xl p-3 shadow-2xl backdrop-blur-md flex flex-col space-y-2.5 text-xs w-56">
          {/* Opacity Slider */}
          <div className="flex items-center justify-between text-[11px] font-semibold text-slate-300">
            <span>Opacidad Satélite</span>
            <span className="font-mono text-sky-400 bg-sky-950/80 px-1.5 py-0.5 rounded border border-sky-800/50">
              {Math.round(opacity * 100)}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(e) => setOpacity(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
          />

          {/* Quick Toggles: Borders & Basemaps */}
          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
            <span className="text-[11px] text-slate-400 font-medium">Fronteras:</span>
            <button
              onClick={() => setShowBorders((prev) => !prev)}
              className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-all border ${
                showBorders
                  ? 'bg-sky-600/30 text-sky-300 border-sky-500/60 shadow-sm'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
              }`}
            >
              {showBorders ? 'Visibles' : 'Ocultas'}
            </button>
          </div>

          {/* Quick Basemap Switcher */}
          <div className="pt-1 flex items-center justify-between space-x-1">
            {[
              { id: 'dark', label: 'Oscuro' },
              { id: 'satellite', label: 'Satélite' },
              { id: 'osm', label: 'Calles' }
            ].map((b) => (
              <button
                key={b.id}
                onClick={() => setBasemap(b.id)}
                className={`flex-1 py-1 rounded text-[10px] font-medium transition-all ${
                  basemap === b.id
                    ? 'bg-sky-600 text-white font-semibold shadow-sm'
                    : 'bg-slate-800/80 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                }`}
              >
                {b.label}
              </button>
            ))}
          </div>
        </div>

        {/* Collapsible Layer & Channel Configuration Sidebar */}
        <ChannelSelector
          channels={channels}
          currentChannel={currentChannel}
          onSelectChannel={(ch) => {
            setCurrentChannel(ch);
          }}
          opacity={opacity}
          onChangeOpacity={setOpacity}
          basemap={basemap}
          onChangeBasemap={setBasemap}
          showBorders={showBorders}
          onToggleBorders={setShowBorders}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        {/* Calibrated Colorbar Legend */}
        <ColorLegend legend={legend} />
      </div>

      {/* Bottom Timeline & Animation Control Bar */}
      <TimelineBar
        frames={frames}
        currentIndex={currentIndex}
        onSelectIndex={(idx) => {
          setIsPlaying(false);
          setCurrentIndex(idx);
        }}
        isPlaying={isPlaying}
        onTogglePlay={() => setIsPlaying((prev) => !prev)}
        onStepBack={handleStepBack}
        onStepForward={handleStepForward}
        fps={fps}
        onChangeFps={setFps}
        frameCount={frameCount}
        onChangeFrameCount={setFrameCount}
        isLoading={isLoading}
        preloadedCount={preloadedCount}
      />

      {/* Scientific & Academic Context Modal */}
      <InfoModal isOpen={infoOpen} onClose={() => setInfoOpen(false)} />
    </div>
  );
}
