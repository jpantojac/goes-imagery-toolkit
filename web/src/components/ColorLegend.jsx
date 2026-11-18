import React from 'react';

export default function ColorLegend({ legend }) {
  if (!legend) return null;

  return (
    <div className="absolute top-4 right-4 z-[1000] bg-slate-900/95 border border-slate-800 rounded-xl p-3 shadow-2xl backdrop-blur-md max-w-xs text-xs">
      <div className="flex items-center justify-between mb-1.5">
        <span className="font-semibold text-slate-200">
          Escala Calibrada ({legend.unit})
        </span>
        <span className="text-[10px] text-sky-400 font-mono bg-sky-950/60 px-1.5 py-0.5 rounded border border-sky-800/40">
          {legend.family === 'noaa' ? 'Paleta NOAA' : 'Paleta Estándar'}
        </span>
      </div>

      <p className="text-[11px] text-slate-400 mb-2 leading-tight">
        {legend.description}
      </p>

      {/* Dynamic CSS Gradient Bar */}
      <div 
        className="h-3.5 w-full rounded shadow-inner border border-slate-700/60 mb-1.5"
        style={{ background: legend.gradient_css }}
      />

      {/* Tick Marks / Labels */}
      <div className="flex justify-between text-[10px] font-mono text-slate-300">
        <span>{legend.min} {legend.unit}</span>
        {legend.stops && legend.stops.length > 2 && (
          <span>{legend.stops[Math.floor(legend.stops.length / 2)].label}</span>
        )}
        <span>{legend.max} {legend.unit}</span>
      </div>
    </div>
  );
}
