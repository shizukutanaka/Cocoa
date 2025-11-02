import React, { useState, useRef, useCallback } from 'react';
import { COLOR_PALETTE } from '@/constants/avatarConstants';

interface DraggableColorProps {
  color: string;
  isSelected: boolean;
  onToggle: (color: string) => void;
  onMove: (fromIndex: number, toIndex: number) => void;
}

export const DraggableColor: React.FC<DraggableColorProps> = ({
  color,
  isSelected,
  onToggle,
  onMove
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const dragRef = useRef<HTMLDivElement>(null);

  const handleDragStart = useCallback((e: React.DragEvent) => {
    setIsDragging(true);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', color);
  }, [color]);

  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);

    const draggedColor = e.dataTransfer.getData('text/plain');
    if (draggedColor && draggedColor !== color) {
      const currentColors = COLOR_PALETTE;
      const fromIndex = currentColors.indexOf(draggedColor as any);
      const toIndex = currentColors.indexOf(color as any);
      onMove(fromIndex, toIndex);
    }
  }, [color, onMove]);

  const handleClick = useCallback(() => {
    onToggle(color);
  }, [color, onToggle]);

  return (
    <div
      ref={dragRef}
      draggable={isSelected}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={handleClick}
      style={{
        backgroundColor: color,
        width: '32px',
        height: '32px',
        borderRadius: '50%',
        border: isSelected
          ? '3px solid #0962F3'
          : dragOver
          ? '3px dashed #0962F3'
          : '2px solid transparent',
        cursor: isSelected ? 'move' : 'pointer',
        opacity: isDragging ? 0.5 : 1,
        transition: 'all 0.2s ease',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
      }}
      aria-label={`${color}を選択${isSelected ? '（選択済み）' : ''}`}
      aria-pressed={isSelected}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleClick();
        }
      }}
    >
      {isSelected && (
        <div
          style={{
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            backgroundColor: '#0962F3',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <span style={{ color: 'white', fontSize: '12px' }}>✓</span>
        </div>
      )}
    </div>
  );
};

interface ColorPaletteProps {
  selectedColors: string[];
  onColorsChange: (colors: string[]) => void;
}

export const DraggableColorPalette: React.FC<ColorPaletteProps> = ({
  selectedColors,
  onColorsChange
}) => {
  const handleColorToggle = useCallback((color: string) => {
    const newColors = selectedColors.includes(color)
      ? selectedColors.filter(c => c !== color)
      : [...selectedColors, color].slice(0, 4);
    onColorsChange(newColors);
  }, [selectedColors, onColorsChange]);

  const handleColorMove = useCallback((fromIndex: number, toIndex: number) => {
    const newColors = [...selectedColors];
    const [movedColor] = newColors.splice(fromIndex, 1);
    newColors.splice(toIndex, 0, movedColor);
    onColorsChange(newColors);
  }, [selectedColors, onColorsChange]);

  return (
    <div
      style={{
        display: 'flex',
        gap: '12px',
        flexWrap: 'wrap',
        padding: '8px',
        border: '1px solid #ddd',
        borderRadius: '8px',
        backgroundColor: '#f8f9fa'
      }}
      role="group"
      aria-label="ドラッグ&ドロップ対応カラーパレット"
    >
      {COLOR_PALETTE.map((color) => (
        <DraggableColor
          key={color}
          color={color}
          isSelected={selectedColors.includes(color)}
          onToggle={handleColorToggle}
          onMove={handleColorMove}
        />
      ))}
    </div>
  );
};
