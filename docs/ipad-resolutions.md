# iPad screen sizes

Apple lists 45 iPad models sharing 10 native screen resolutions. Beam groups models with the same family and size into 17 choices. Checked against [Apple’s model list](https://support.apple.com/en-us/108043) and the linked technical specifications on 2026-09-19. The catalog works offline; it does not infer a model from a stream request.

1. On the iPad, open **Settings → General → About → Model Name**.
2. In Beam, open **iPad screen**, choose that model group, and select **Use this size**.
3. In Moonlight settings, choose **Resolution → Custom**, enter the shown width and height, and use **60 FPS**. These are landscape dimensions.
4. Quit the running desktop session in Moonlight, then launch **Beam Desktop** again. Merely resuming keeps the previous request.

Both ends must match. Setting only the desktop leaves black borders when Moonlight still requests 720p or 1080p. Beam reports the last mismatch even after disconnect.

These are screen pixel counts, not text sizes. Beam uses desktop scaling for readable controls while keeping native capture sharp. Choosing the same size preserves an existing custom scale. Audio and music stream alongside the picture.

For a model not listed, choose **Use Moonlight Full** and select **Full** in Moonlight. Beam follows the dimensions Moonlight requests. Older iPads are included for reference; check the App Store for Moonlight compatibility before setup.

![Beam iPad screen picker](assets/ipad-picker.png)

## iPad

| Model | Landscape custom resolution |
| --- | --- |
| [iPad (A16)](https://support.apple.com/122240) | **2360 × 1640** |
| [iPad (10th generation)](https://support.apple.com/kb/SP884) | **2360 × 1640** |
| [iPad (9th generation)](https://support.apple.com/kb/SP849) | **2160 × 1620** |
| [iPad (8th generation)](https://support.apple.com/kb/SP822) | **2160 × 1620** |
| [iPad (7th generation)](https://support.apple.com/kb/SP807) | **2160 × 1620** |
| [iPad (6th generation)](https://support.apple.com/kb/SP774) | **2048 × 1536** |
| [iPad (5th generation)](https://support.apple.com/kb/SP751) | **2048 × 1536** |
| [iPad (4th generation)](https://support.apple.com/kb/SP662) | **2048 × 1536** |
| [iPad (3rd generation)](https://support.apple.com/kb/SP647) | **2048 × 1536** |
| [iPad 2](https://support.apple.com/kb/sp622) | **1024 × 768** |
| [iPad](https://support.apple.com/kb/SP580) | **1024 × 768** |

## iPad Air

| Model | Landscape custom resolution |
| --- | --- |
| [iPad Air 13-inch (M4)](https://support.apple.com/126472) | **2732 × 2048** |
| [iPad Air 13-inch (M3)](https://support.apple.com/122242) | **2732 × 2048** |
| [iPad Air 13-inch (M2)](https://support.apple.com/119893) | **2732 × 2048** |
| [iPad Air 11-inch (M4)](https://support.apple.com/126471) | **2360 × 1640** |
| [iPad Air 11-inch (M3)](https://support.apple.com/122241) | **2360 × 1640** |
| [iPad Air 11-inch (M2)](https://support.apple.com/119894) | **2360 × 1640** |
| [iPad Air (5th generation)](https://support.apple.com/kb/SP866) | **2360 × 1640** |
| [iPad Air (4th generation)](https://support.apple.com/kb/SP828) | **2360 × 1640** |
| [iPad Air (3rd generation)](https://support.apple.com/kb/SP787) | **2224 × 1668** |
| [iPad Air 2](https://support.apple.com/kb/SP708) | **2048 × 1536** |
| [iPad Air](https://support.apple.com/kb/SP692) | **2048 × 1536** |

## iPad mini

| Model | Landscape custom resolution |
| --- | --- |
| [iPad mini (A17 Pro)](https://support.apple.com/121456) | **2266 × 1488** |
| [iPad mini (6th generation)](https://support.apple.com/kb/SP850) | **2266 × 1488** |
| [iPad mini (5th generation)](https://support.apple.com/kb/SP788) | **2048 × 1536** |
| [iPad mini 4](https://support.apple.com/kb/SP725) | **2048 × 1536** |
| [iPad mini 3](https://support.apple.com/kb/SP709) | **2048 × 1536** |
| [iPad mini 2](https://support.apple.com/kb/SP693) | **2048 × 1536** |
| [iPad mini](https://support.apple.com/kb/SP661) | **1024 × 768** |

## iPad Pro

| Model | Landscape custom resolution |
| --- | --- |
| [iPad Pro 13-inch (M5)](https://support.apple.com/125407) | **2752 × 2064** |
| [iPad Pro 13-inch (M4)](https://support.apple.com/119891) | **2752 × 2064** |
| [iPad Pro 12.9-inch (6th generation)](https://support.apple.com/kb/SP883) | **2732 × 2048** |
| [iPad Pro 12.9-inch (5th generation)](https://support.apple.com/kb/SP844) | **2732 × 2048** |
| [iPad Pro 12.9-inch (4th generation)](https://support.apple.com/kb/SP815) | **2732 × 2048** |
| [iPad Pro 12.9-inch (3rd generation)](https://support.apple.com/kb/SP785) | **2732 × 2048** |
| [iPad Pro 12.9-inch (2nd generation)](https://support.apple.com/kb/SP761) | **2732 × 2048** |
| [iPad Pro (12.9-inch)](https://support.apple.com/kb/SP723) | **2732 × 2048** |
| [iPad Pro 11-inch (M5)](https://support.apple.com/125406) | **2420 × 1668** |
| [iPad Pro 11-inch (M4)](https://support.apple.com/119892) | **2420 × 1668** |
| [iPad Pro 11-inch (4th generation)](https://support.apple.com/kb/SP882) | **2388 × 1668** |
| [iPad Pro 11-inch (3rd generation)](https://support.apple.com/kb/SP843) | **2388 × 1668** |
| [iPad Pro 11-inch (2nd generation)](https://support.apple.com/kb/SP814) | **2388 × 1668** |
| [iPad Pro 11-inch](https://support.apple.com/kb/SP784) | **2388 × 1668** |
| [iPad Pro (10.5-inch)](https://support.apple.com/kb/SP762) | **2224 × 1668** |
| [iPad Pro (9.7-inch)](https://support.apple.com/kb/SP739) | **2048 × 1536** |

## If the screen still does not fit

- Confirm Beam says **Moonlight matches** after a new launch.
- Avoid 16:9 presets on an iPad with a different aspect ratio. A high pixel count alone does not remove borders.
- Increase desktop or application text scaling instead of reducing the stream to 720p.
- A static wallpaper reduces constant motion; video wallpapers are optional and are not disabled globally by the installer.
- End the stream to restore the local monitor layout, including ultrawide monitors.
