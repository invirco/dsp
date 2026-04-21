<?xml version="1.0"?>

<xsl:stylesheet version="1.0" xmlns:adi="http://www.analog.com/archdef" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<adi:version file-version="3.0.2.0" />

<!-- ************************************************************************ -->
<!-- ******* AnomalySiliconRevisions.xsl                                      -->
<!-- ************************************************************************ -->
<!-- ******* XML Transformation sheet for displaying the compiler XML files   -->
<!-- ******* 1)  Links to the HTML formatted display of the complete          -->
<!-- *******     processor anomaly dictionary with info for all tools.        -->
<!-- ******* 2)  Displays specific to this file:                              -->
<!-- *******  a) List of supported silicon revision with color highlight of   -->
<!-- *******     default.                                                     -->
<!-- *******  b) Library paths per silicon revision (inflection points)       -->
<!-- *******  c) Shows "per silicon revision" reference chart for compiler    -->
<!-- *******     and assembler                                                -->
<!-- *******  d) compiler only information (verbose)                          -->
<!-- *******     shows ones on by default (and which -si-revisions apply it)  -->
<!-- *******  e) assembler only information (verbose)                         -->
<!-- *******  f) feature-macros                                               -->
<!-- *******  g) versions of files used for the content in the display        -->
<!-- ******* Viewing silicon revision anomaly views was verified using        -->
<!-- ******* browsers:                                                        -->
<!-- *******     Google Chrome 2.0.172.39                                     -->
<!-- *******     Microsoft Internet Explorer 6.0 SP2                          -->
<!-- *******     Mozilla FireFox 3.5.2                                        -->
<!-- *******     Microsoft Internet Explorer 7.0 (not yet tested)             -->
<!-- *******     Microsoft Internet Explorer 8.0 (not yet tested)             -->
<!-- *******                                                                  -->
<!-- ******* Copyright 2009-2024 Analog Devices, Inc.  All rights reserved.   -->
<!-- ************************************************************************ -->

<!-- *****  Globals  ***** -->
<xsl:variable name="filename-version" select="//cces-compiler-xml/version/@file-version" />

  <!-- *********************** -->
  <!-- ******  main    ******* -->
  <!-- *********************** -->

  <xsl:template match ="/">
   <html xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

   <head>
   <style>
   p {font-size: 140%; font-weight: bold}
   </style>
   </head>

   <body bgcolor="#99cccc">
   <xsl:apply-templates select="cces-compiler-xml"/>
   </body>
   </html>
  </xsl:template>

  <!-- ****************************************** -->
  <!-- ******   cces-compiler-xml         ******* -->
  <!-- ******       *-compiler.xml        ******* -->
  <!-- ****************************************** -->

  <xsl:template match="cces-compiler-xml">
   <!-- display core specific anomaly details and feature macros -->
   <xsl:if test="child::core">
    <xsl:apply-templates select="core"/>
   </xsl:if>
   <xsl:if test="not(child::core)">
    <xsl:apply-templates select="architecture">
     <xsl:with-param name="coreID">0</xsl:with-param>
     <xsl:with-param name="isMC">0</xsl:with-param>
     <xsl:with-param name="family">0</xsl:with-param>
    </xsl:apply-templates>    
   </xsl:if>
   <!-- display file versions -->
   <P/><HR size="4"/>
   <a name="VERSIONS">
    <p>File Versions</p>
    <xsl:text>Information extracted from:</xsl:text>
    <li>
     <xsl:value-of select="@name"/>, Version <xsl:value-of select="$filename-version"/>
    </li>
    <xsl:if test="child::core">
      <xsl:for-each select="child::core">
        <xsl:if test="child::cces-anomaly-dictionary">
          <xsl:variable name="dictionaryFilename" select="child::cces-anomaly-dictionary/@name" />
          <li>
            <xsl:value-of select="$dictionaryFilename"/>, Version <xsl:value-of select="document($dictionaryFilename)/cces-dictionary-xml/version/@file-version"/>
          </li>
        </xsl:if>
      </xsl:for-each>
    </xsl:if>
    <xsl:if test="not(child::core)">
     <xsl:variable name="dictionaryFilename" select="cces-anomaly-dictionary/@name" />
     <li>
      <xsl:value-of select="$dictionaryFilename"/>, Version <xsl:value-of select="document($dictionaryFilename)/cces-dictionary-xml/version/@file-version"/>
     </li>
    </xsl:if>
    </a>
  </xsl:template>
  
  <!-- ****************************************** -->
  <!-- ******   core                      ******* -->
  <!-- ****************************************** -->

  <xsl:template match="core">
   <xsl:apply-templates select="architecture">
    <xsl:with-param name="coreID"><xsl:value-of select="@id"/></xsl:with-param>
    <xsl:with-param name="isMC">1</xsl:with-param>
    <xsl:with-param name="family"><xsl:value-of select="@family"/></xsl:with-param>
   </xsl:apply-templates>
  </xsl:template>

  <!-- ****************************************** -->
  <!-- ******   architecture              ******* -->
  <!-- ****************************************** -->

  <xsl:template match="architecture">
   <xsl:param name="isMC" /> <!-- 0 (single core) or 1 (multicore) -->
   <xsl:param name="coreID" />
   <xsl:param name="family" />
   <xsl:variable name="processor" select="@name" />

   <!-- Display processor and core details as h1 -->
   <P/><HR size="4"/>
   <h1>
    <xsl:if test="$isMC &gt; 0">
     <xsl:value-of select="@name"/> -
     <xsl:if test="$family != ''">
      <xsl:value-of select="$family"/>
     </xsl:if>
     <xsl:if test="contains($coreID, ',')">
      <xsl:text> cores </xsl:text>
     </xsl:if>
     <xsl:if test="not(contains($coreID, ','))">
      <xsl:text> core </xsl:text>
     </xsl:if>
     <xsl:value-of select="$coreID"/>
    </xsl:if>
    <xsl:if test="$isMC &lt; 1">
     <xsl:value-of select="@name"/>
    </xsl:if>
   </h1>
   <P/><HR size="4"/>
   <br/>

   <!-- Display anomaly view table -->
   <table border="1" bgcolor="#cccccc" width="50%" cellpadding="6" cellspacing="6">
    <tr align="center">
     <th rowspan="10"><h1>Views</h1></th>
    </tr>
    <xsl:if test="$family != 'ARM'">
     <th colspan="2"><b><big><a href="#{generate-id(following-sibling::silicon-revisions)}">Silicon Revisions</a></big></b></th>
     <tr align="center"><th colspan="2"><b><big><a href="#LIBPATH{generate-id(following-sibling::silicon-revisions)}">Libraries</a></big></b></th></tr>
     <tr align="center"><th colspan="2"><b><big><a href="#PERSILICON{generate-id(following-sibling::silicon-revisions)}">Anomalies By Silicon Revision</a></big></b></th></tr>
     <tr align="center"><th colspan="2"><b><big><a href="#COMPILER_ONLY{generate-id(following-sibling::silicon-revisions)}">Compiler [verbose]</a></big></b></th></tr>
     <tr align="center"><th colspan="2"><b><big><a href="#ASSEMBLER_ONLY{generate-id(following-sibling::silicon-revisions)}">Assembler [verbose]</a></big></b></th></tr>
    </xsl:if>
     <tr align="center">
      <th colspan="2"><b><big><a href="#{generate-id(following-sibling::feature-macros)}">Predefined Macros</a></big></b></th>
     </tr>
    <xsl:if test="following-sibling::cces-anomaly-dictionary">
     <tr align="center">
      <th colspan="2"><b><big><xsl:apply-templates select="following-sibling::cces-anomaly-dictionary"/></big></b></th>
     </tr>
    </xsl:if>
    <tr align="center">
     <th colspan="2"><b><big><a href="#VERSIONS">File Versions</a></big></b></th>
    </tr>
   </table>

   <!-- Display revision and anomaly info -->
   <xsl:if test="$family != 'ARM'">
    <xsl:apply-templates select="following-sibling::silicon-revisions">
     <xsl:with-param name="processor">
       <xsl:value-of select="$processor"/>
     </xsl:with-param>
     <xsl:with-param name="coreID">
       <xsl:value-of select="$coreID"/>
     </xsl:with-param>
     <xsl:with-param name="isMC">
       <xsl:value-of select="$isMC"/>
     </xsl:with-param>
     <xsl:with-param name="compiler-driver">
       <xsl:value-of select="following-sibling::compiler/compiler-location-tools/@driver-path" />
     </xsl:with-param>
     <xsl:with-param name="family">
       <xsl:value-of select="$family"/>
     </xsl:with-param>
    </xsl:apply-templates>
   </xsl:if>

   <!-- Display the predefined macros -->
   <a name="{generate-id(following-sibling::feature-macros)}">
    <p>Predefined macros</p>
    <xsl:apply-templates select="following-sibling::feature-macros">
     <xsl:with-param name="processor">
       <xsl:value-of select="$processor"/>
     </xsl:with-param>
     <xsl:with-param name="coreID">
       <xsl:value-of select="$coreID"/>
     </xsl:with-param>
     <xsl:with-param name="isMC">
       <xsl:value-of select="$isMC"/>
     </xsl:with-param>
    </xsl:apply-templates>
   </a>
  </xsl:template>

  <!-- ****************************************** -->
  <!-- ******   feature-macros            ******* -->
  <!-- ****************************************** -->

  <xsl:template match="feature-macros">
   <xsl:param name="processor"/>
   <xsl:param name="coreID"/>
   <xsl:param name="isMC"/> <!-- 0 (single core) or 1 (multicore) -->
    <xsl:text>The assembler and compiler automatically define the following processor feature macros when building for </xsl:text>
    <xsl:value-of select="$processor"/>
    <xsl:if test="$isMC &gt; 0">
     <xsl:if test="contains($coreID, ',')">
      <xsl:text> cores </xsl:text>
     </xsl:if>
     <xsl:if test="not(contains($coreID, ','))">
      <xsl:text> core </xsl:text>
     </xsl:if>
     <xsl:value-of select="$coreID"/>
    </xsl:if>
    <xsl:text>.</xsl:text>
   <br/>
   <xsl:text>Processor predefined macros are in addition to any anomaly specific macros that are defined by the assembler or compiler.</xsl:text>
   <br/><br/>
   <table border="2" bordercolor="black" width="25%" cellpadding="6" cellspacing="0">
   <thead bgcolor="#efd6bc">
   <tr>
         <th width="15%" align="center" valign="center"><b><big><br></br>Macros Defined</big></b></th>
   </tr>
   </thead>
   <xsl:for-each select="macro">
      <tr>
         <td width="15%" align="center" valign="center">
            <big><xsl:value-of select="@name"/><xsl:text>=</xsl:text><xsl:value-of select="@value"/></big>
         </td>
      </tr>
   </xsl:for-each>
   </table>
  </xsl:template>

  <xsl:template match="cces-anomaly-dictionary">
   <!-- provide a link to access the dictionary in the *-anomaly.xml file -->
   <a>
    <xsl:attribute name="href">
     <xsl:value-of select="@name"/>
    </xsl:attribute>
    <p>Silicon Anomaly Support - All Tools</p>
   </a>
  </xsl:template>

  <!-- *********************************** -->
  <!-- ******  Silicon Revisions   ******* -->
  <!-- ******   *-compiler.xml     ******* -->
  <!-- *********************************** -->

  <xsl:template match="silicon-revisions">
   <xsl:param name="processor"/>
   <xsl:param name="coreID"/>
   <xsl:param name="isMC"/> <!-- 0 (single core) or 1 (multicore) -->
   <xsl:param name="compiler-driver"/>
   <xsl:param name="family"/>

   <xsl:variable name="silicon-revision-default" select="@command-line-default" />

	<a name="{generate-id()}">
	<p>Supported Silicon Revisions</p>

	<xsl:text>Supported silicon revision are listed in the table below. CrossCore Embedded Studio projects use the project Processor Settings to select the required target. New projects are set for the default revision, </xsl:text><xsl:value-of select="$silicon-revision-default"/><xsl:text>. This default revision is also used when </xsl:text>

   <xsl:if test="$family = 'ARM'">
    <xsl:text>-msi-revision</xsl:text>
   </xsl:if>
   <xsl:if test="$family != 'ARM'">
    <xsl:text>-si-revision</xsl:text>
   </xsl:if>
   <xsl:text> is omitted on a command-line build.</xsl:text>

	<br/>
   <br/>

	<table border="2" bordercolor="black" width="25%" cellpadding="6" cellspacing="0">
	<thead bgcolor="#efd6bc">
	<tr>
       	<th width="15%" align="center"><b><big>Silicon Revision</big></b></th>
	</tr>
	</thead>

	<xsl:for-each select="silicon">
		<tr>

		<xsl:if test="$silicon-revision-default=@revision">
			<td width="15%" align="left"><big><a href="#SIREV{@revision}{generate-id()}"><xsl:value-of select="@revision"></xsl:value-of></a></big><small> [DEFAULT]</small></td>
		</xsl:if>
		<xsl:if test="$silicon-revision-default!=@revision">
			<xsl:if test="@revision='none'">
				<td width="15%" align="left"><big><xsl:value-of select="@revision"></xsl:value-of></big></td>
			</xsl:if>
			<xsl:if test="@revision!='none'">
				<td width="15%" align="left"><big><a href="#SIREV{@revision}{generate-id()}"><xsl:value-of select="@revision"></xsl:value-of></a></big></td>
			</xsl:if>
		</xsl:if>
		</tr>
	</xsl:for-each>
	</table>
</a>

	<!-- ********************** -->
	<!-- ****   LIB PATH   **** -->
	<!-- ********************** -->

	<a name="LIBPATH{generate-id()}">
	<p>Libraries and Silicon Revisions</p>

	<xsl:text>CrossCore Embedded Studio is supplied with multiple copies of libraries built for various parts, build configurations and silicon revisions. 
	The compiler driver determines which library search path to pass to the linker (using the -L switch).</xsl:text>

   <xsl:if test="$compiler-driver!=''">
	 <xsl:text>The compiler driver for the </xsl:text> 
	 <xsl:value-of select="$processor"/> is '<xsl:value-of select="$compiler-driver"/>'<xsl:text>.</xsl:text>
   </xsl:if>

	<xsl:text>
	Relying on the compiler driver to automatically manage the library path selection is the recommended build method. 
	The following chart shows the subfolders used for library paths for the </xsl:text> <xsl:value-of select="$processor"/>.

	<h3>Warning: If the build calls the linker directly instead of relying on the compiler driver, the user needs to manage the library search paths manually.</h3>

	<table border="2" bordercolor="black" width="50%" cellpadding="6" cellspacing="0">
	<thead bgcolor="#efd6bc">
	<tr>
       	<th width="15%" align="left"><b><big>Silicon Revision</big></b></th>
        <th width="25%" align="left"><b><big>Library Path</big></b></th>
        <th width="10%" align="left"><b><big>Inflection Point *</big></b></th>
	</tr>
	</thead>

	<xsl:for-each select="silicon">
		<tr>
		<xsl:if test="$silicon-revision-default=@revision">
			<td width="15%" bgcolor="#dec5ab" align="left"><big><a href="#SIREV{@revision}{generate-id()}"><xsl:value-of select="@revision"></xsl:value-of></a> *</big><small> [DEFAULT]</small></td>
		</xsl:if>
		<xsl:if test="$silicon-revision-default!=@revision">
			<xsl:if test="@revision='none'">
				<td width="15%" align="left"><big><xsl:value-of select="@revision"></xsl:value-of></big></td>
			</xsl:if>
			<xsl:if test="@revision!='none'">
				<td width="15%" align="left"><big><a href="#SIREV{@revision}{generate-id()}"><xsl:value-of select="@revision"></xsl:value-of></a></big></td>
			</xsl:if>
		</xsl:if>

		<xsl:if test="string-length(@lib-path) &gt; 1">
			<td width="30%" align="left"><big><xsl:value-of select="@lib-path"></xsl:value-of></big></td>
		</xsl:if>

		<xsl:if test="string-length(@revision) &gt; 1">
			<xsl:if test="(string(@revision) = 'none')" >
			<td align="center"><big>no workarounds</big></td>
			</xsl:if>
			<xsl:if test="(string(@revision) = 'any')" >
			<td align="center"><big>all workarounds</big></td>
			</xsl:if>
			<xsl:if test="( string(@revision) != 'none' and string(@revision) != 'any' )" >
			<xsl:choose>
				<xsl:when test="not((preceding-sibling::*/@lib-path) = @lib-path)">
					<td align="CENTER"><big>new version</big></td>
				</xsl:when>
			 	<xsl:otherwise>
					<td align="CENTER"><big>--</big></td>
			 	</xsl:otherwise>
			</xsl:choose>
			</xsl:if>
		</xsl:if>
		</tr>
	</xsl:for-each>
	</table>

	<br></br>
	<br></br>	
	<xsl:text>
	* Each subfolder represents what is called a library inflection point and includes a complete set of libraries that are appropriate for one or more silicon revision builds. 
	For every application build one of these subfolders is passed to the linker as the library search path (using -L).
   Parts or silicon revisions that are very similar in terms of the anomaly workarounds they require are supported using the same inflection point. When a silicon revision uses a new inflection point, it is indicated in the chart above with </xsl:text> <b>'new version'</b> in the inflection point column.

   <xsl:if test="$family != 'ARM'">
	<h3>Tip: Debug Libraries</h3>

	<xsl:text>The 'Use Debug System libraries' project checkbox (-add-debug-libpaths compiler switch) causes the compiler driver to pass an additional library search path to the linker.  This path is passed before the path found in the chart above and is the same path with '/debug' appended. Using </xsl:text> <xsl:value-of select="$processor"/>, -si revision 'any' as an example:

	<br></br><br></br>
	<table border="2" bordercolor="black" width="65%" cellpadding="6" cellspacing="0">
	<thead bgcolor="#efd6bc">
	<tr>
        <th width="25%" align="left"><b><big>Library Path</big></b></th>
        <th width="40%" align="left"><b><big>When Enabled for Debug</big></b></th>
	</tr>
	</thead>

	<xsl:for-each select="silicon">
		<xsl:if test="(string(@revision) = 'any')" >
		<tr>
		<td>-L <xsl:value-of select="@lib-path"></xsl:value-of></td>
		<td>-L <xsl:value-of select="@lib-path"></xsl:value-of>/debug -L <xsl:value-of select="@lib-path"></xsl:value-of></td>
		</tr>
		</xsl:if>
	</xsl:for-each>

	</table>
  </xsl:if>

</a>
	<!-- ************************* -->
	<!-- ****   PER SILICON   **** -->
	<!-- ****    OVERVIEW     **** -->
	<!-- ************************* -->

	<a name="PERSILICON{generate-id()}">
	<p>Silicon Revision Anomaly Chart for <xsl:value-of select="$processor"/></p>
	<br></br>
	</a>

	<!-- ********************************* -->
	<!-- *******     Sub menu      ******* -->
	<!-- ********************************* -->

	<table border="1" bgcolor="#cccccc" width="30%" cellpadding="6" cellspacing="6">

		<tr align="center" valign="center">
			<th align="center" valign="center">
			<big><xsl:value-of select="$processor"/>
			<br></br>Select by Silicon Revision</big></th>
		</tr>

		<xsl:for-each select="silicon">
			<tr align="center">
				<xsl:if test="@revision != 'none'">
				<th colspan="2"><b><big><a href="#SIREV{@revision}{generate-id()}"> 
					<xsl:value-of select="@revision"/>
					</a></big></b></th>
				</xsl:if>
			</tr>
		</xsl:for-each>
	</table>

   <xsl:if test="following-sibling::cces-anomaly-dictionary">
    <xsl:variable name="dictionary-filename"      select="following-sibling::cces-anomaly-dictionary/@name" />

	<br></br><br></br>
	<!-- Link to the analog web where the errata sheets for this family is -->
	<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary">
		<xsl:if test="string-length(@adi-web-link) > 0">
			<xsl:text>Consult the errata sheets on the Analog Devices web site for further information:</xsl:text><br></br>
			<a>
				<xsl:attribute name="href"><xsl:value-of select="@adi-web-link"/></xsl:attribute>
				<xsl:attribute name="target">_blank</xsl:attribute>
				<b><xsl:value-of select="@title"/></b>
			</a>
		</xsl:if>
	</xsl:for-each>

	<br></br>

	<!-- ******************************************** -->
	<!-- *******  Table per Silicon Revision  ******* -->
	<!-- ******************************************** -->

	<xsl:for-each select="silicon">
	<xsl:variable name="silicon-revision" select="@revision"/> 
	<xsl:variable name="num-workarounds" select="count(workaround)"/> 

	<xsl:if test="$silicon-revision != 'none'">

		<a name="SIREV{@revision}{generate-id()}"/> 
		<br></br>

		<table border="2" bordercolor="black" width="90%" cellpadding="6" cellspacing="0">
		<thead bgcolor="#efd6bc">
		<tr>
	       	<th width="5%"  align="center" valign="center"><b><big>Silicon Revision</big></b></th>
       		<th width="10%" align="center" valign="center"><b><big>Anomaly ID</big></b></th>
	        <th width="25%" align="center" valign="center"><b><big><a href="#COMPILER_ONLY">Compiler Options</a></big></b></th>
	        <th width="25%" align="center" valign="center"><b><big><a href="#ASSEMBLER_ONLY">Assembler Detect Options</a></big></b></th>
	        <th width="25%" align="center" valign="center"><b><big><a href="#ASSEMBLER_ONLY">Assembler Workaround Options</a></big></b></th>
		</tr>
		</thead>

		<!-- ******************* -->
		<!-- *** Per ID row  *** -->
		<!-- ******************* -->

		<xsl:for-each select="(workaround)">
			<!-- Extraneous 'N' no longer appears in the Blackfin *-compiler.xml ... this can now be widened to include all -->
			<xsl:if test="( string(@compiler-default)='Y' or string(@compiler-default)='N' or string(@assembler-detect-default)='Y' or string(@assembler-workaround-default)='Y' or string(@assembler-detect-default)='N' or string(@assembler-workaround-default)='N' )" >
		<tr>
			<td width="5%" align="center" valign="center" bgcolor="#af968c">
			<big>"<xsl:value-of select="$silicon-revision"/>"</big>
			</td>

			<td width="10%" align="center" valign="center" bgcolor="#ffe6cc">
				<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
					<xsl:value-of select="@id"/><br></br>
				</xsl:for-each>
			</td>

			<!-- *************************** -->
			<!-- *** Compiler Workaround *** -->
			<!-- *************************** -->
			<td width="25%" align="left" valign="center">
				<xsl:if test="string-length(@compiler-default) = 0">
					<xsl:text>&#160;&#160;&#160;</xsl:text>
				</xsl:if>
				<xsl:if test="string(@compiler-default)='Y'" >
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:value-of select="@compiler-option"/>
					</xsl:for-each>
				</xsl:if>
				<xsl:if test="string(@compiler-default)='N'" >
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:value-of select="@compiler-option"/> [optional]<br></br>
					</xsl:for-each>
				</xsl:if>
			</td>

			<!-- ************************* -->
			<!-- *** Assembler Detect  *** -->
			<!-- ************************* -->
			<td width="25%" align="left" valign="center">
				<xsl:if test="string-length(@assembler-detect-default) = 0">
					<xsl:text>&#160;&#160;&#160;</xsl:text><br></br>
				</xsl:if>
				<xsl:if test="string(@assembler-detect-default)='Y'" >
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:value-of select="@assembler-detect-option"/><br></br>
					</xsl:for-each>
				</xsl:if>				
				<xsl:if test="string(@assembler-detect-default)='N'" >
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:value-of select="@assembler-detect-option"/> [optional]<br></br>
					</xsl:for-each>
				</xsl:if>				
			</td>

			<!-- ***************************** -->
			<!-- *** Assembler Workaround  *** -->
			<!-- ***************************** -->
			<td width="25%" align="left" valign="center">

				<xsl:if test="string-length(@assembler-workaround-default) = 0">
					<xsl:text>&#160;&#160;&#160;</xsl:text><br></br>
				</xsl:if>

				<xsl:if test="string(@assembler-workaround-default)='Y'" >
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:value-of select="@assembler-workaround-option"/><br></br>
					</xsl:for-each>
				</xsl:if>
				<xsl:if test="string(@assembler-workaround-default)='N'" >
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:value-of select="@assembler-workaround-option"/> [optional]<br></br>
					</xsl:for-each>
				</xsl:if>
			</td>
		</tr>
		</xsl:if>
		</xsl:for-each>
	</table>
	</xsl:if>
	</xsl:for-each>


	<!-- ********************** -->
	<!-- ****   COMPILER   **** -->
	<!-- ********************** -->

	<a name="COMPILER_ONLY{generate-id()}">
	<p><xsl:value-of select="$processor"/> Chart (Compiler-Only)</p>
	</a>

	<li>The following chart is specific to the compiler anomaly workarounds for the <b><xsl:value-of select="$processor"/></b> processor.</li>
	<li>The <b>Silicon Revisions</b> column shows the list of silicon revisions that enable the workaround by default.</li>
	
	<br></br><li>Silicon revisions for the <xsl:value-of select="$processor"/> processor that apply workarounds are:</li>
		<xsl:for-each select="silicon">
			<xsl:if test="@revision!='none'">
				<br></br><xsl:text>&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;&#160;</xsl:text><a href="#SIREV{@revision}{generate-id()}"><xsl:value-of select="@revision"></xsl:value-of></a>
			</xsl:if>
		</xsl:for-each>
	<li>The <b>-si-revision "any"</b> applies each workaround by default.</li>

	<br></br>
	<br></br>
	<!-- Link to the analog web where the errata sheets for this family is -->
	<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary">
		<xsl:if test="string-length(@adi-web-link) > 0">
			<xsl:text>Consult the errata sheets on the Analog Devices web site for further information:</xsl:text>
			<br></br>
			<a>
				<xsl:attribute name="href"><xsl:value-of select="@adi-web-link"/></xsl:attribute>
				<xsl:attribute name="target">_blank</xsl:attribute>
				<b><xsl:value-of select="@title"/></b>
			</a>
		</xsl:if>
	</xsl:for-each>

	<br></br><br></br><table border="2" bordercolor="black" width="90%" cellpadding="6" cellspacing="0">
	<thead bgcolor="#efd6bc">
	<tr>
       	<th width="35%" align="center"><b><big>Anomaly<br></br>Compiler Switch and Define</big></b></th>
        <th width="35%" align="center"><b><big>Compiler Behavior</big></b></th>
        <th width="20%" align="center"><b><big><xsl:value-of select="$processor"/><br></br>Silicon Revisions</big></b></th>
	</tr>
	</thead>

 	<xsl:for-each select="silicon[@revision='any']/workaround">

		<!-- The typical case for compiler verbose is for sub-heading 'Applies by default to:' followed by the list of silicon revisions, -->
		<!-- but make sure there is at least one 'Y' default to list before committing to that sub-heading.                               -->
		<xsl:variable name="compiler-default-count-y" select="count(silicon/workaround[@ix=current()/@ix][@compiler-default='Y'])"/>

		<xsl:if test="string-length(@compiler-default) > 0">
		<xsl:variable name="workaround-ix" select="@ix"/> 
		<tr>
			<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
				<td width="35%" align="left" valign="center" bgcolor="#ffe6cc">
				<h3><xsl:value-of select="@id"/></h3>
				<small><xsl:value-of select="@summary"/></small>
				<br></br><br></br><b><xsl:value-of select="@compiler-option"/></b>
				<br></br><br></br><small><i><xsl:value-of select="@compiler-defs"/></i></small>
				<!-- <h4>ix=[<xsl:value-of select="current()/@ix"/>]</h4> --> 
				</td>

				<td width="35%" align="left" valign="top">
				<small><xsl:value-of select="@compiler-behavior"/></small>
				</td>
			</xsl:for-each>

			<!-- get list of silicon revisions for "current()/@ix" (can't define function a la 2.0 ...) ... maybe keys -->
			<td width="20%" align="left" valign="top">
				<xsl:if test="( $compiler-default-count-y > 0 )" >
					<i>Applies by default to:</i>
					<xsl:for-each select="silicon">
						<xsl:variable name="silicon-revision" select="@revision"/> 
						<xsl:if test="$silicon-revision != 'none'">
							<xsl:for-each select="(workaround[@compiler-default='Y'])" >
								<xsl:if test="@ix=$workaround-ix">
									<br></br>-si-revision "<xsl:value-of select="$silicon-revision"/>"
								</xsl:if>
							</xsl:for-each>
						</xsl:if>
					</xsl:for-each>
				</xsl:if>
				<xsl:if test="( $compiler-default-count-y = 0 )" >
					[optional]
				</xsl:if>
			</td>
		</tr>
		</xsl:if>
	</xsl:for-each>

	</table>

	<!-- *********************** -->
	<!-- ****   ASSEMBLER   **** -->
	<!-- *********************** -->

	<a name="ASSEMBLER_ONLY{generate-id()}">
	<p><xsl:value-of select="$processor"/> Chart (Assembler-Only)</p>
	<br></br>
	</a>

	<xsl:variable name="assembler-detect-count-y"     select="count(silicon[@revision='any']/workaround[@assembler-detect-default='Y'])"/>
	<xsl:variable name="assembler-detect-count-n"     select="count(silicon[@revision='any']/workaround[@assembler-detect-default='N'])"/>
	<xsl:variable name="assembler-workaround-count-y" select="count(silicon[@revision='any']/workaround[@assembler-workaround-default='Y'])"/>
	<xsl:variable name="assembler-workaround-count-n" select="count(silicon[@revision='any']/workaround[@assembler-workaround-default='N'])"/>

	<!-- **************************************************************** -->
	<!-- special case the processors where the assembler takes no actions -->
	<!-- **************************************************************** -->

	<xsl:if test="( $assembler-detect-count-y = 0 and $assembler-detect-count-n = 0 and $assembler-workaround-count-y = 0 and $assembler-workaround-count-n = 0)">
	 	There are no assembler detection or workaround switches for the <b><xsl:value-of select="$processor"/></b> processor.
	</xsl:if>

	<!-- ************************************************************************************ -->
	<!-- display the chart for processors where one or more anomalies have assembler actions  -->
	<!-- ************************************************************************************ -->

<xsl:if test="( $assembler-detect-count-y > 0 or $assembler-detect-count-n > 0 or $assembler-workaround-count-y > 0 or $assembler-workaround-count-n > 0)">
		The following chart is specific to the assembler switches that are available for the <b><xsl:value-of select="$processor"/></b> processor.

	<!-- Link to the analog web where the errata sheets for this family is -->
	<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary">
		<xsl:if test="string-length(@adi-web-link) > 0">
			<br></br><br></br>
			<xsl:text>Consult the errata sheets on the Analog Devices web site for further information:</xsl:text><br></br>
			<a>
				<xsl:attribute name="href"><xsl:value-of select="@adi-web-link"/></xsl:attribute>
				<xsl:attribute name="target">_blank</xsl:attribute>
				<b><xsl:value-of select="@title"/></b>
			</a>
		</xsl:if>
	</xsl:for-each>

	<br></br>
	<br></br>
	<table border="2" bordercolor="black" width="90%" cellpadding="6" cellspacing="0">
	<thead bgcolor="#efd6bc">
	<tr>
       	<th width="15%" align="left"><b><big>Anomaly</big></b></th>
        <th width="35%" align="left"><b><big>Assembler Behavior</big></b></th>
        <th width="40%" align="left"><b><big>Assembler Switches<br></br>for -si-revision 'any'</big></b></th>
	</tr>
	</thead>

 	<xsl:for-each select="silicon">
		<xsl:if test="@revision='any'">
			<xsl:for-each select="(workaround)">

				<!-- **************************************************************** -->
				<!-- ********** both assembler detect and workaround option ********* -->
				<!-- **************************************************************** -->
				<xsl:if test="( string-length(@assembler-workaround-default) > 0 and string-length(@assembler-detect-default) > 0)">
				<tr>
					<td width="15%" align="left" valign="center" bgcolor="#cfb69c">
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<h3><xsl:value-of select="@id"/></h3>
						<small><xsl:value-of select="@summary"/></small>
<!--						<h4>ix=[<xsl:value-of select="current()/@ix"/>]</h4> -->
					</xsl:for-each>
					</td>

				<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
					<xsl:if test="string-length(@assembler-behavior) > 0">
						<td width="35%" align="left" valign="top">
						<small><xsl:value-of select="@assembler-behavior"/></small>
						</td>
					</xsl:if>
				</xsl:for-each>

					<td style="padding:0 0 0 0;">
					<table border="0" width="100%" cellpadding="6" cellspacing="0">
						<tr>
						<!-- (1) ******* detect ******* -->

					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<td width="25%" align="left">
						<xsl:value-of select="@assembler-detect-option"/>
						</td>
					</xsl:for-each>

							<xsl:if test="@assembler-detect-default='Y'">
								<td width="15%" align="left"><i>default</i></td>
							</xsl:if>
							<xsl:if test="@assembler-detect-default='N'">
								<td width="15%" align="left">[optional]</td>
							</xsl:if>
						<!-- (2) ******* workaround ******* -->
						<tr>
							<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
							<td width="25%" align="left">
							<xsl:value-of select="@assembler-workaround-option"/>
							</td>
							</xsl:for-each>

							<xsl:if test="@assembler-workaround-default='Y'">
								<td width="15%" align="left"><i>default</i></td>
							</xsl:if>
							<xsl:if test="@assembler-workaround-default='N'">
								<td width="15%" align="left">[optional]</td>
							</xsl:if>
						</tr>
						</tr>
					</table>
					</td>
				</tr>
				</xsl:if>

				<!-- ******************************************************** -->
				<!-- ************* assembler detect option only ************* -->
				<!-- ******************************************************** -->
				<xsl:if test="( string-length(@assembler-detect-default) > 0 and string-length(@assembler-workaround-default) = 0)">
				<tr>
					<td width="30%" align="left" valign="center" bgcolor="#cfb69c">
						<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
							<h3><xsl:value-of select="@id"/></h3>
							<small><xsl:value-of select="@summary"/></small>
<!--							<h4>ix=[<xsl:value-of select="current()/@ix"/>]</h4> -->
							</xsl:for-each>
						</td>

				<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:if test="string-length(@assembler-behavior) > 0">
							<td width="35%" align="left" valign="top">
							<small><xsl:value-of select="@assembler-behavior"/></small>
							</td>
						</xsl:if>
						<xsl:if test="string-length(@assembler-behavior) = 0">
							<td width="35%" align="left" valign="top">
							<xsl:text>WARNING: xsl detected a missing assembler-behavior description</xsl:text>
							</td>
						</xsl:if>
				</xsl:for-each>

				<td style="padding:0 0 0 0;">
				<table border="0" width="100%" cellpadding="6" cellspacing="0">
				<tr>
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:if test="string-length(@assembler-detect-option) > 0">
							<td width="25%" align="left">
								<xsl:value-of select="@assembler-detect-option"/>
							</td>
						</xsl:if>

						<xsl:if test="string-length(@assembler-detect-option) = 0">
							<td width="30%" align="left">
								<xsl:text>ERROR for index </xsl:text><xsl:value-of select="current()/@ix"/>
								<br></br><xsl:text>XSL detected assembler-detect-default in compiler.xml, but unable to locate assembler-detect-option in dictionary.</xsl:text>
							</td>
						</xsl:if>
				</xsl:for-each>
						<xsl:if test="@assembler-detect-default='Y'">
							<td width="15%" align="left"><i>default</i></td>
						</xsl:if>
						<xsl:if test="@assembler-detect-default='N'">
							<td width="15%" align="left">[optional]</td>
						</xsl:if>
</tr>
					</table>
					</td>
				</tr>
				</xsl:if>

				<!-- ******************************************************** -->
				<!-- ************* assembler workaround option only ********* -->
				<!-- ******************************************************** -->
				<xsl:if test="( string-length(@assembler-detect-default) = 0 and string-length(@assembler-workaround-default) > 0)">
				<tr>
					<td width="30%" align="left" valign="center" bgcolor="#cfb69c">
						<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
							<h3><xsl:value-of select="@id"/></h3>
							<small><xsl:value-of select="@summary"/></small>
<!--							<h4>ix=[<xsl:value-of select="current()/@ix"/>]</h4> -->
							</xsl:for-each>
						</td>

				<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:if test="string-length(@assembler-behavior) > 0">
							<td width="35%" align="left" valign="top">
							<small><xsl:value-of select="@assembler-behavior"/></small>
							</td>
						</xsl:if>
						<xsl:if test="string-length(@assembler-behavior) = 0">
							<td width="35%" align="left" valign="top">
							<small><xsl:text>WARNING: missing assembler-behavior description</xsl:text></small>
							</td>
						</xsl:if>
				</xsl:for-each>

				<td style="padding:0 0 0 0;">
				<table border="0" width="100%" cellpadding="6" cellspacing="0">
				<tr>
					<xsl:for-each select="document($dictionary-filename)/cces-dictionary-xml/anomaly-dictionary/anomaly[@ix=current()/@ix]">
						<xsl:if test="string-length(@assembler-workaround-option) > 0">
							<td width="15%" align="left"><big>
								<xsl:value-of select="@assembler-workaround-option"/>
							</big></td>
						</xsl:if>
						<xsl:if test="string-length(@assembler-workaround-option) = 0">
							<td width="30%" align="left"><big>
								<xsl:text>ERROR for index </xsl:text><xsl:value-of select="current()/@ix"/>
								<br></br><xsl:text>assembler-workaround-default in compiler.xml, but unable to locate assembler-workaround-option in dictionary.</xsl:text>
							</big></td>
						</xsl:if>
					</xsl:for-each>
						<xsl:if test="@assembler-workaround-default='Y'">
							<td width="30%" align="left"><i>default</i></td>
						</xsl:if>
						<xsl:if test="@assembler-workaround-default='N'">
							<td width="30%" align="left">[optional]</td>
						</xsl:if>
				</tr>
				</table>
				</td>
			</tr>
			</xsl:if>
			</xsl:for-each>
		</xsl:if>
	</xsl:for-each>
	</table>
  </xsl:if>
  </xsl:if>

  </xsl:template> 

</xsl:stylesheet>
