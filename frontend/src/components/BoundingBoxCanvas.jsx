import React, { useRef, useEffect } from 'react';

export default function BoundingBoxCanvas({ imageUrl, bbox, label, zones = [] }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!imageUrl) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = imageUrl;

    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;

      // Draw base image
      ctx.drawImage(img, 0, 0);

      // Draw zones if provided
      zones.forEach((z) => {
        if (!z.boundary_polygon || z.boundary_polygon.length < 3) return;
        ctx.beginPath();
        const poly = z.boundary_polygon;
        ctx.moveTo(poly[0][0], poly[0][1]);
        for (let i = 1; i < poly.length; i++) {
          ctx.lineTo(poly[i][0], poly[i][1]);
        }
        ctx.closePath();

        const isBay = z.zone_type === 'parking_bay';
        const isFire = z.zone_type === 'fire_lane';
        ctx.lineWidth = 2;
        ctx.strokeStyle = isFire ? 'rgba(239, 68, 68, 0.8)' : isBay ? 'rgba(14, 165, 233, 0.8)' : 'rgba(234, 179, 8, 0.8)';
        ctx.fillStyle = isFire ? 'rgba(239, 68, 68, 0.15)' : isBay ? 'rgba(14, 165, 233, 0.15)' : 'rgba(234, 179, 8, 0.15)';
        ctx.fill();
        ctx.stroke();

        // Label zone
        ctx.font = 'bold 14px sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.fillText(z.name || z.zone_id, poly[0][0] + 5, poly[0][1] + 18);
      });

      // Draw vehicle bbox if provided
      if (bbox && bbox.length === 4) {
        const [x1, y1, x2, y2] = bbox;
        const width = x2 - x1;
        const height = y2 - y1;

        const isViolation = label === 'violation';
        const isRisk = label === 'risk';
        const color = isViolation ? '#ef4444' : isRisk ? '#f59e0b' : '#10b981';

        ctx.lineWidth = 3;
        ctx.strokeStyle = color;
        ctx.strokeRect(x1, y1, width, height);

        // Header pill
        ctx.fillStyle = color;
        const tagText = `${label ? label.toUpperCase() : 'VEHICLE'}`;
        ctx.font = 'bold 13px sans-serif';
        const textWidth = ctx.measureText(tagText).width;
        ctx.fillRect(x1, Math.max(0, y1 - 24), textWidth + 12, 24);

        ctx.fillStyle = '#ffffff';
        ctx.fillText(tagText, x1 + 6, Math.max(16, y1 - 7));
      }
    };
  }, [imageUrl, bbox, label, zones]);

  if (!imageUrl) {
    return (
      <div className="flex items-center justify-center h-64 bg-slate-900 rounded-lg border border-slate-700 text-slate-500 text-sm">
        No Snapshot Available
      </div>
    );
  }

  return (
    <div className="relative rounded-lg overflow-hidden border border-slate-700 bg-black flex items-center justify-center">
      <canvas ref={canvasRef} className="max-h-[500px] w-auto max-w-full object-contain" />
    </div>
  );
}
