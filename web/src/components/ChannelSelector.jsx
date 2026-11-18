import React, { useState } from 'react';
import { Sliders, Map, Eye, Flame, Droplets, CloudSun, EyeOff } from 'lucide-react';

export default function ChannelSelector({
  channels = [],
  currentChannel,
  onSelectChannel,
  opacity,
  onChangeOpacity,
  basemap,
  onChangeBasemap,
  showBorders,
  onToggleBorders,
  isOpen,
  onClose
}) {
  const [activeTab, setActiveTab] = useState('ir'); // 'vis', 'wv', 'ir'

  if (!isOpen) return null;

  // Group channels by category
  const visibleBands = channels.filter(c => ['C01', 'C02', 'C03', 'C04', 'C05', 'C06'].includes(c.channel));
  const waterVaporBands = channels.filter(c => ['C08', 'C09', 'C10'].includes(c.channel));
  const infraredBands = channels.filter(c => ['C07', 'C11', 'C12', 'C13', 'C14', 'C15', 'C16'].includes(c.channel));

  const currentTabBands = 
    activeTab === 'vis' ? visibleBands :
    activeTab === 'wv' ? waterVaporBands : infraredBands;

  return (
    <aside className="absolute top-16 left-4 z-[1050] w-80 bg-slate-900/95 border border-slate-800 rounded-2xl shadow-2xl backdrop-blur-md flex flex-col max-h-[calc(100vh-140px)] overflow-hidden transition-all duration-200">
      {/* Panel Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sliders className="w-4 h-4 text-sky-400" />
          <h2 className="text-sm font-bold text-white tracking-wide">Configuración de Capas</h2>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white text-xs px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700"
        >
          ✕
        </button>
      </div>

      <div className="p-4 overflow-y-auto space-y-5">
        {/* Transparency / Opacity Slider */}
        <div className="space-y-2">
          <div className="flex justify-between items-center text-xs">
            <span className="font-semibold text-slate-300 flex items-center space-x-1.5">
              <Eye className="w-3.5 h-3.5 text-sky-400" />
              <span>Opacidad Satelital</span>
            </span>
            <span className="font-mono text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800/50">
              {Math.round(opacity * 100)}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(e) => onChangeOpacity(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        {/* Vector Overlays: Political Borders */}
        <div className="space-y-2 pt-2 border-t border-slate-800">
          <span className="text-xs font-semibold text-slate-300">
            Capas Vectoriales
          </span>
          <label className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 cursor-pointer hover:bg-slate-950">
            <span className="text-xs text-slate-300">Fronteras y Límites Políticos</span>
            <input
              type="checkbox"
              checked={showBorders}
              onChange={(e) => onToggleBorders(e.target.checked)}
              className="w-4 h-4 accent-sky-500 rounded cursor-pointer"
            />
          </label>
        </div>

        {/* Basemap Selection */}
        <div className="space-y-2">
          <span className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
            <Map className="w-3.5 h-3.5 text-sky-400" />
            <span>Mapa Base</span>
          </span>
          <div className="grid grid-cols-3 gap-1.5 text-xs">
            {[
              { id: 'dark', label: 'Dark Matter' },
              { id: 'satellite', label: 'Satélite' },
              { id: 'osm', label: 'Calles OSM' }
            ].map(b => (
              <button
                key={b.id}
                onClick={() => onChangeBasemap(b.id)}
                className={`py-1.5 px-2 rounded-lg text-center font-medium transition-all ${
                  basemap === b.id
                    ? 'bg-sky-600 text-white shadow-md'
                    : 'bg-slate-800/80 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                }`}
              >
                {b.label}
              </button>
            ))}
          </div>
        </div>

        {/* ABI Spectral Bands Category Tabs */}
        <div className="space-y-3 pt-2 border-t border-slate-800">
          <span className="text-xs font-semibold text-slate-300">
            Canales ABI GOES (C01 - C16)
          </span>

          <div className="grid grid-cols-3 gap-1 p-1 bg-slate-950/80 rounded-xl border border-slate-800 text-[11px] font-medium">
            <button
              onClick={() => setActiveTab('vis')}
              className={`py-1.5 rounded-lg flex items-center justify-center space-x-1 transition-all ${
                activeTab === 'vis' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <CloudSun className="w-3.5 h-3.5" />
              <span>Visible</span>
            </button>
            <button
              onClick={() => setActiveTab('wv')}
              className={`py-1.5 rounded-lg flex items-center justify-center space-x-1 transition-all ${
                activeTab === 'wv' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Droplets className="w-3.5 h-3.5" />
              <span>Vapor</span>
            </button>
            <button
              onClick={() => setActiveTab('ir')}
              className={`py-1.5 rounded-lg flex items-center justify-center space-x-1 transition-all ${
                activeTab === 'ir' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Flame className="w-3.5 h-3.5" />
              <span>Térmico</span>
            </button>
          </div>

          {/* List of Channels in Active Category */}
          <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
            {currentTabBands.map(ch => {
              const isSelected = currentChannel === ch.channel;
              return (
                <button
                  key={ch.channel}
                  onClick={() => onSelectChannel(ch.channel)}
                  className={`w-full text-left p-2 rounded-xl transition-all border flex items-center justify-between ${
                    isSelected
                      ? 'bg-sky-950/70 border-sky-500 text-white shadow-md'
                      : 'bg-slate-800/40 border-slate-800/80 text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <div className="flex flex-col">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-xs text-sky-400">{ch.channel}</span>
                      <span className="text-xs font-medium truncate max-w-[150px]">{ch.name}</span>
                    </div>
                    <span className="text-[10px] text-slate-400 truncate max-w-[200px] mt-0.5">
                      {ch.description}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800 shrink-0">
                    {ch.wavelength_um} µm
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </aside>
  );
}
