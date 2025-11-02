import React, { useState, useCallback } from 'react';

interface ColorPickerProps {
  color: string;
  onChange: (color: string) => void;
}

export const ColorPicker: React.FC<ColorPickerProps> = ({ color, onChange }) => {
  const [isOpen, setIsOpen] = useState(false);

  const handleColorClick = useCallback(() => {
    setIsOpen(!isOpen);
  }, [isOpen]);

  const handleColorSelect = useCallback((newColor: string) => {
    onChange(newColor);
    setIsOpen(false);
  }, [onChange]);

  return (
    <div className="color-picker">
      <button
        type="button"
        className="color-button"
        style={{ backgroundColor: color }}
        onClick={handleColorClick}
      />
      {isOpen && (
        <div className="color-palette">
          {['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'].map(c => (
            <button
              key={c}
              type="button"
              className="color-option"
              style={{ backgroundColor: c }}
              onClick={() => handleColorSelect(c)}
            />
          ))}
        </div>
      )}
    </div>
  );
};
