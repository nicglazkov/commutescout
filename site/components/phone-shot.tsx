import Image from "next/image";

// A real app screenshot, framed. Not a drawn phone: the frame is a thin
// hairline, the screen's own corner radius and a soft shadow, so the
// screenshot is the object. Every app screenshot on the site goes through
// this so they line up. The screenshots are captured by
// scripts/capture_app_shots.sh from the simulator and the emulator with
// a demo status bar and a simulated location.
//
// Both platforms' screenshots are close to 9:19.5 (640 x 1387-1391), so
// one aspect ratio serves all of them.
type Props = {
  src: string;
  alt: string;
  /** Largest rendered width in px (a cap and the image `sizes`); height follows.
   *  The width itself comes from className (e.g. "w-full", "w-[46%]"), so it
   *  can shrink with its container on a phone. */
  width?: number;
  className?: string;
  priority?: boolean;
};

export function PhoneShot({ src, alt, width = 300, className = "", priority }: Props) {
  return (
    <div
      className={`min-w-0 overflow-hidden rounded-[13%/6%] border border-cs-line-strong bg-cs-surface-2 shadow-[var(--cs-shadow-md)] ${className}`}
      style={{ maxWidth: width }}
    >
      <Image
        src={src}
        alt={alt}
        width={640}
        height={1389}
        sizes={`${width}px`}
        className="block aspect-[640/1389] h-auto w-full object-cover"
        priority={priority}
      />
    </div>
  );
}
