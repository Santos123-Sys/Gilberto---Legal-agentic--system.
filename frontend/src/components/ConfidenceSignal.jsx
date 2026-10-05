import React from 'react'

export function ConfidenceSignal({ score, confidence, classification, size = 'md' }) {
  const sizeConfig = {
    sm: { ring: 40, font: 'text-xs', barHeight: 'h-1.5' },
    md: { ring: 56, font: 'text-sm', barHeight: 'h-2' },
    lg: { ring: 80, font: 'text-lg', barHeight: 'h-3' },
  }

  const cfg = sizeConfig[size]
  const scoreNumber = Number(score)
  const safeScore = Number.isFinite(scoreNumber) ? Math.min(10, Math.max(0, scoreNumber)) : 0
  const confidenceNumber = Number(confidence)
  const safeConfidence = Number.isFinite(confidenceNumber) ? Math.min(5, Math.max(0, confidenceNumber)) : 0

  const confidenceColor = safeConfidence >= 4 ? '#10b981' : safeConfidence >= 3 ? '#f59e0b' : '#ef4444'
  const classificationColor =
    classification === 'Crítico' ? '#ef4444' :
    classification === 'Relevante' ? '#f59e0b' : '#10b981'

  const radius = (cfg.ring - 6) / 2
  const circumference = 2 * Math.PI * radius
  const fill = (safeScore / 10) * circumference

  return (
    <div className="flex items-center gap-4">
      {/* Score ring */}
      <div className="relative" style={{ width: cfg.ring, height: cfg.ring }}>
        <svg width={cfg.ring} height={cfg.ring} className="transform -rotate-90">
          <circle
            cx={cfg.ring / 2} cy={cfg.ring / 2} r={radius}
            fill="none" stroke="#1e293b" strokeWidth="4"
          />
          <circle
            cx={cfg.ring / 2} cy={cfg.ring / 2} r={radius}
            fill="none" stroke={classificationColor} strokeWidth="4"
            strokeDasharray={`${fill} ${circumference}`}
            strokeLinecap="round"
            className="transition-all duration-1000"
          />
        </svg>
        <span
          className={`absolute inset-0 flex items-center justify-center font-bold ${cfg.font}`}
          style={{ color: classificationColor }}
        >
          {safeScore.toFixed(1)}
        </span>
      </div>

      {/* Confidence + classification */}
      <div className="space-y-1.5">
        <div>
          <div className="flex justify-between items-center gap-4 mb-1">
            <span className="text-xs text-slate-500">Confidence</span>
            <span className="text-xs font-medium" style={{ color: confidenceColor }}>
              {safeConfidence}/5 {safeConfidence >= 4 ? 'High' : safeConfidence >= 3 ? 'Medium' : 'Low'}
            </span>
          </div>
          <div className={`w-32 bg-slate-700 rounded-full ${cfg.barHeight}`}>
            <div
              className={`${cfg.barHeight} rounded-full transition-all duration-1000`}
              style={{ width: `${(safeConfidence / 5) * 100}%`, backgroundColor: confidenceColor }}
            />
          </div>
        </div>

        <div
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
          style={{ backgroundColor: `${classificationColor}20`, color: classificationColor }}
        >
          <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: classificationColor }} />
          {classification}
        </div>

        {safeConfidence < 3 && (
          <p className="text-[10px] text-yellow-400 flex items-center gap-1">
            <span>⚠</span> Low confidence — human review recommended
          </p>
        )}
      </div>
    </div>
  )
}
