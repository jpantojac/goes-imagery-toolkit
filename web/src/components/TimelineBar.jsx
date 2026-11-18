import React from 'react';
import { 
  Play, 
  Pause, 
  SkipBack, 
  SkipForward, 
  Download, 
  Gauge, 
  Film, 
  RefreshCw,
  FileDown
} from 'lucide-react';

export default function TimelineBar({
  frames,
  currentIndex,
  onSelectIndex,
  isPlaying,
  onTogglePlay,
  onStepBack,
  onStepForward,
  fps,
  onChangeFps,
  frameCount,
  onChangeFrameCount,
  isLoading,
  preloadedCount
}) {
  const currentFrame = frames[currentIndex] || null;
  const totalFrames = frames.length;

  const handleDownload = (format = 'png') => {
    if (!currentFrame) return;
    const url = format === 'tif' && currentFrame.tif_url ? currentFrame.tif_url : currentFrame.url;
    const link = document.createElement('a');
    link.href = url;
    link.download = currentFrame.filename.replace('.png', `.${format}`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <footer className="h-20 bg-slate-900/95 border-t border-slate-800/90 px-4 py-2 flex flex-col justify-between z-30 shadow-2xl backdrop-blur-md">
      {/* Top row: Interactive Scrubber Slider and Status */}
      <div className="flex items-center space-x-3 w-full">
        {/* Current frame indicator */}
        <div className="text-[11px] font-mono text-slate-300 w-24 shrink-0 flex items-center space-x-1.5">
          <span className="text-sky-400 font-bold">{totalFrames > 0 ? currentIndex + 1 : 0}</span>
          <span className="text-slate-500">/</span>
          <span>{totalFrames} frames</span>
        </div>

        {/* Timeline Scrubber Slider */}
        <div className="relative flex-1 flex items-center">
          <input
            type="range"
            min="0"
            max={totalFrames > 0 ? totalFrames - 1 : 0}
            value={totalFrames > 0 ? currentIndex : 0}
            onChange={(e) => onSelectIndex(parseInt(e.target.value, 10))}
            disabled={totalFrames <= 1 || isLoading}
            className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer disabled:cursor-not-allowed z-10"
          />

          {/* Loading / Preloading progress bar under the slider */}
          {isLoading && totalFrames > 0 && (
            <div 
              className="absolute left-0 h-2 bg-sky-900/40 rounded-lg pointer-events-none transition-all duration-150"
              style={{ width: `${(preloadedCount / totalFrames) * 100}%` }}
            />
          )}
        </div>

        {/* Timestamp of the hovered/selected frame */}
        <div className="text-[11px] font-mono text-sky-300 bg-slate-950/80 px-2.5 py-0.5 rounded border border-slate-800 shrink-0">
          {currentFrame?.iso_utc ? currentFrame.iso_utc.slice(11, 16) + ' UTC' : '--:-- UTC'}
        </div>
      </div>

      {/* Bottom row: Playback Buttons, FPS, Frame Count, Download */}
      <div className="flex items-center justify-between">
        {/* Left: Playback Controls */}
        <div className="flex items-center space-x-2">
          {/* Step Back */}
          <button
            onClick={onStepBack}
            disabled={totalFrames <= 1}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title="Cuadro previo (Flecha Izquierda)"
          >
            <SkipBack className="w-4 h-4" />
          </button>

          {/* Play / Pause Toggle */}
          <button
            onClick={onTogglePlay}
            disabled={totalFrames <= 1}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center space-x-1.5 text-xs transition-all shadow-md ${
              isPlaying
                ? 'bg-amber-600 hover:bg-amber-500 text-white shadow-amber-900/30'
                : 'bg-sky-600 hover:bg-sky-500 text-white shadow-sky-900/30'
            } disabled:opacity-40 disabled:cursor-not-allowed`}
            title="Reproducir / Pausar (Barra Espaciadora)"
          >
            {isPlaying ? (
              <>
                <Pause className="w-4 h-4 fill-white" />
                <span>Pausar</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Animar</span>
              </>
            )}
          </button>

          {/* Step Forward */}
          <button
            onClick={onStepForward}
            disabled={totalFrames <= 1}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title="Cuadro siguiente (Flecha Derecha)"
          >
            <SkipForward className="w-4 h-4" />
          </button>

          {isLoading && (
            <div className="flex items-center space-x-1 text-[11px] text-sky-400 font-medium pl-2">
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              <span>Precargando {preloadedCount}/{totalFrames}...</span>
            </div>
          )}
        </div>

        {/* Center: Frame Count Selection */}
        <div className="hidden sm:flex items-center space-x-1.5 bg-slate-950/70 border border-slate-800/80 px-2 py-1 rounded-lg text-xs">
          <Film className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-slate-400 font-medium mr-1">Cuadros:</span>
          {[6, 12, 24, 48].map((count) => (
            <button
              key={count}
              onClick={() => onChangeFrameCount(count)}
              className={`px-2 py-0.5 rounded font-mono font-medium transition-colors ${
                frameCount === count
                  ? 'bg-sky-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {count}
            </button>
          ))}
        </div>

        {/* Right: Speed (FPS) & Download Menu */}
        <div className="flex items-center space-x-3">
          {/* FPS Selector */}
          <div className="flex items-center space-x-1.5 bg-slate-950/70 border border-slate-800/80 px-2 py-1 rounded-lg text-xs">
            <Gauge className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400 font-medium mr-1">FPS:</span>
            {[3, 5, 8, 12, 20].map((rate) => (
              <button
                key={rate}
                onClick={() => onChangeFps(rate)}
                className={`px-1.5 py-0.5 rounded font-mono font-medium transition-colors ${
                  fps === rate
                    ? 'bg-sky-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {rate}
              </button>
            ))}
          </div>

          {/* Download Current Product */}
          <div className="flex items-center space-x-1">
            <button
              onClick={() => handleDownload('png')}
              disabled={!currentFrame}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white disabled:opacity-40 transition-colors flex items-center space-x-1 text-xs"
              title="Descargar imagen PNG georreferenciada actual"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden md:inline font-mono">PNG</span>
            </button>
            {currentFrame?.tif_url && (
              <button
                onClick={() => handleDownload('tif')}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors flex items-center space-x-1 text-xs"
                title="Descargar ráster GeoTIFF para QGIS / ArcGIS"
              >
                <FileDown className="w-3.5 h-3.5 text-emerald-400" />
                <span className="hidden md:inline font-mono text-emerald-400">GeoTIFF</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
}
