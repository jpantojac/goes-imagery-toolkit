import React, { useState, useEffect, useRef, useCallback } from 'react';
import Header from './components/Header';
import MapViewer from './components/MapViewer';
import ChannelSelector from './components/ChannelSelector';
import ColorLegend from './components/ColorLegend';
import TimelineBar from './components/TimelineBar';
import InfoModal from './components/InfoModal';
import { 
  fetchBounds, 
  fetchChannels, 
  fetchFrames, 
  fetchLegend, 
  fetchHealth 
} from './services/apiClient';

export default function App() {
  // Application State
  const [channels, setChannels] = useState([]);
  const [currentChannel, setCurrentChannel] = useState('C13');
  const [frameCount, setFrameCount] = useState(24);
  const [frames, setFrames] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [fps, setFps] = useState(8);
  const [opacity, setOpacity] = useState(0.85);
  const [basemap, setBasemap] = useState('dark');
  const [boundsMeta, setBoundsMeta] = useState(null);
  const [legend, setLegend] = useState(null);
  const [apiOnline, setApiOnline] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [preloadedCount, setPreloadedCount] = useState(0);
  const [coords, setCoords] = useState({ lat: null, lon: null });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);

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
        channelMeta={currentChannelMeta}
        coords={coords}
        currentFrame={currentFrame}
        apiOnline={apiOnline}
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
          onMouseMove={setCoords}
          onPreloadProgress={setPreloadedCount}
        />

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
