Qsaharaserver.exe -p \\.\portname -s 13:%~dp0image\xbl_s_devprg_ns.melf
fh_loader.exe --port=\\.\portname --setactivepartition=1 --zlpawarehost=1 --sendxml=rawprogram_save_persist_unsparse0.xml --sendxml=rawprogram1.xml --sendxml=rawprogram2.xml --sendxml=rawprogram3.xml --sendxml=rawprogram4.xml --sendxml=rawprogram5.xml --sendxml=patch0.xml --sendxml=patch1.xml --sendxml=patch2.xml --sendxml=patch3.xml --sendxml=patch4.xml --sendxml=patch5.xml --search_path=%~dp0image --noprompt --showpercentagecomplete --memoryname=UFS --reset


