import React, { useCallback, useRef, useEffect } from 'react';

interface SliderProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  label?: string;
}

export const Slider: React.FC<SliderProps> = ({
  value,
  min,
  max,
  step = 1,
  onChange,
  label
}) => {
  const sliderRef = useRef<HTMLInputElement>(null);

  const handleChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    onChange(Number(event.target.value));
  }, [onChange]);

  return (
    <div className="slider">
      {label && <label className="slider-label">{label}</label>}
      <input
        ref={sliderRef}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleChange}
        className="slider-input"
      />
      <span className="slider-value">{value}</span>
    </div>
  );
};
