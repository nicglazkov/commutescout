import Image from "next/image";

// A phone screenshot inside a plain dark frame. Every app screenshot on
// the site goes through this so the frames match: same radius, same
// bezel, same shadow. The screenshots themselves are captured by
// scripts/capture_app_shots.sh from the simulator and the emulator with
// a demo status bar (9:41, full battery) and a simulated location, so
// nothing personal is in them.
//
// Both platforms' screenshots are close to 9:19.5, so one aspect ratio
// serves all of them and the frames in a row line up.
type Props = {
  src: string;
  alt: string;
  /** Rendered width in px at the largest breakpoint; height follows. */
  width?: number;
  className?: string;
  priority?: boolean;
};

export function PhoneShot({ src, alt, width = 300, className = "", priority }: Props) {
  const height = Math.round(width * 2.17);
  return (
    <div
      className={`shrink-0 rounded-[2.4rem] bg-cs-navy p-[6px] shadow-2xl shadow-cs-navy/40 ring-1 ring-white/15 ${className}`}
      style={{ width }}
    >
      <div className="overflow-hidden rounded-[2rem] bg-cs-bg">
        <Image
          src={src}
          alt={alt}
          width={width * 2}
          height={height * 2}
          className="block h-auto w-full"
          priority={priority}
        />
      </div>
    </div>
  );
}
