import React from 'react';
import { motion, useMotionValue, useTransform } from 'framer-motion';
import { Check, X, HelpCircle } from 'lucide-react';

interface SwipeCardProps {
    name: string;
    onSwipe: (direction: 'like' | 'dislike' | 'maybe') => void;
}

export const SwipeCard: React.FC<SwipeCardProps> = ({ name, onSwipe }) => {
    const x = useMotionValue(0);
    const rotate = useTransform(x, [-200, 200], [-30, 30]);
    const opacity = useTransform(x, [-200, -150, 0, 150, 200], [0, 1, 1, 1, 0]);
    const background = useTransform(
        x,
        [-200, 0, 200],
        ['rgb(254, 202, 202)', 'rgb(255, 255, 255)', 'rgb(187, 247, 208)']
    );

    const handleDragEnd = (_: any, info: any) => {
        if (info.offset.x > 100) {
            onSwipe('like');
        } else if (info.offset.x < -100) {
            onSwipe('dislike');
        }
    };

    return (
        <motion.div
            style={{ x, rotate, opacity, background }}
            drag="x"
            dragConstraints={{ left: 0, right: 0 }}
            onDragEnd={handleDragEnd}
            className="absolute w-full h-full max-w-sm rounded-3xl shadow-xl flex flex-col items-center justify-center p-8 border-4 border-white cursor-grab active:cursor-grabbing"
        >
            <h1 className="text-5xl font-bold text-gray-800 mb-4">{name}</h1>

            <div className="absolute bottom-8 flex gap-8">
                <button
                    onClick={() => onSwipe('dislike')}
                    className="p-4 rounded-full bg-red-100 text-red-500 hover:bg-red-200 transition-colors"
                >
                    <X size={32} />
                </button>
                <button
                    onClick={() => onSwipe('maybe')}
                    className="p-4 rounded-full bg-gray-100 text-gray-500 hover:bg-gray-200 transition-colors"
                >
                    <HelpCircle size={32} />
                </button>
                <button
                    onClick={() => onSwipe('like')}
                    className="p-4 rounded-full bg-green-100 text-green-500 hover:bg-green-200 transition-colors"
                >
                    <Check size={32} />
                </button>
            </div>
        </motion.div>
    );
};
