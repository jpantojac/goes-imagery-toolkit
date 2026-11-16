import React from 'react';
import { BookOpen, Server, Layers, Cpu, ExternalLink, X } from 'lucide-react';

export default function InfoModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-sky-950 text-sky-400 rounded-lg border border-sky-800/50">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">GOES Imagery Toolkit & Web GIS</h3>
              <p className="text-xs text-slate-400 font-mono">Arquitectura Distribuida y Visualización de Teledetección</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs text-slate-300 leading-relaxed">
          {/* Scientific Context */}
          <div>
            <h4 className="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
              <Cpu className="w-4 h-4 text-sky-400" />
              <span>Contexto Científico y Teledetección</span>
            </h4>
            <p>
              Esta plataforma procesa, calibra y visualiza flujos de radiación provenientes de los radiómetros 
              <strong> NOAA Advanced Baseline Imager (ABI)</strong> a bordo de <strong>GOES-16 y GOES-19</strong>. 
              El pipeline calibra los 16 canales espectrales (Visible, Infrarrojo Cercano, Vapor de Agua Troposférico 
              e Infrarrojo Térmico) aplicando curvas cromáticas meteorológicas estandarizadas (McIDAS BD, Oklahoma Convective, NOAA NESDIS) 
              y georreferenciación precisa en proyección WGS84 (EPSG:4326).
            </p>
          </div>

          {/* Microservices Architecture */}
          <div>
            <h4 className="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
              <Server className="w-4 h-4 text-indigo-400" />
              <span>Arquitectura de Microservicios Desacoplados</span>
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800">
                <span className="font-bold text-sky-400 block mb-1">1. Pipeline (`app`)</span>
                <p className="text-[11px] text-slate-400">
                  Descarga concurrente S3 (NOAA Open Data) y procesamiento ráster con GDAL, Basemap y GeoTIFF.
                </p>
              </div>
              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800">
                <span className="font-bold text-indigo-400 block mb-1">2. REST API (`api`)</span>
                <p className="text-[11px] text-slate-400">
                  Backend asíncrono FastAPI con OpenAPI/Swagger, streaming de cuadros con caché ETag y catálogo espacial.
                </p>
              </div>
              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800">
                <span className="font-bold text-emerald-400 block mb-1">3. Web GIS (`web`)</span>
                <p className="text-[11px] text-slate-400">
                  Motor React + Leaflet con doble búfer para animación a 60 FPS sin parpadeo y control de capas.
                </p>
              </div>
            </div>
          </div>

          {/* Keyboard Shortcuts */}
          <div>
            <h4 className="text-sm font-semibold text-white mb-2 flex items-center space-x-2">
              <Layers className="w-4 h-4 text-amber-400" />
              <span>Atajos de Teclado Operacionales</span>
            </h4>
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800 flex justify-between">
                <span className="text-slate-400">Barra Espaciadora:</span>
                <span className="text-white font-semibold">Play / Pausa</span>
              </div>
              <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800 flex justify-between">
                <span className="text-slate-400">Flecha Derecha:</span>
                <span className="text-white font-semibold">Cuadro Siguiente</span>
              </div>
              <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800 flex justify-between">
                <span className="text-slate-400">Flecha Izquierda:</span>
                <span className="text-white font-semibold">Cuadro Anterior</span>
              </div>
              <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800 flex justify-between">
                <span className="text-slate-400">Rueda del Ratón:</span>
                <span className="text-white font-semibold">Zoom Dinámico</span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between text-xs text-slate-400">
          <span>GOES Satellite Imagery Toolkit &bull; Portafolio de Investigación</span>
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1 text-sky-400 hover:text-sky-300 font-medium"
          >
            <span>Ver Documentación OpenAPI (/docs)</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </div>
  );
}
