import PyInstaller.__main__
import platform
import os

if __name__ == "__main__":
    print("Starting PyInstaller build for Agapay Studio...")
    
    # Path separator for PyInstaller --add-data argument
    sep = ';' if platform.system() == 'Windows' else ':'
    
    # Base PyInstaller arguments
    args = [
        'WEBV2.py',
        '--name=AgapayStudio',
        '--onefile',       # Bundle everything into a single executable
        '--windowed',      # Hide the console window (for GUI application)
        '--clean',         # Clean PyInstaller cache before building
        f'--add-data=templates{sep}templates',
        f'--add-data=static{sep}static',
    ]
    
    # Add optional directories if they exist

    if os.path.exists('legal-corpus'):
        args.append(f'--add-data=legal-corpus{sep}legal-corpus')
        
    if os.path.exists('localfiles'):
        # Just creating an empty directory reference or adding specific default files
        args.append(f'--add-data=localfiles{sep}localfiles')
        
    # Standard hidden imports for the framework
    hidden_imports = [
        'src',
        'flask',
        'dotenv',
        'tkinter',
        'queue',
        'uuid',
        'threading',
        # Add any other modules that PyInstaller might miss dynamically here
    ]
    
    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')
        
    print(f"Running PyInstaller with arguments: {args}")
    
    # Execute PyInstaller
    PyInstaller.__main__.run(args)
    
    print("\nBuild complete. Check the 'dist' directory for your executable.")
