<?xml version="1.0"?>

<xsl:stylesheet version="1.0" xmlns:adi="http://www.analog.com/archdef" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<adi:version file-version="1.00" />

<!-- ************************************************************************ -->
<!-- ******* AnomalyFamily.xsl                                                -->
<!-- ************************************************************************ -->
<!-- ******* XML Transformation sheet for help links to the processor family. -->
<!-- *******                                                                  -->
<!-- ******* Copyright 2009-2011 Analog Devices, Inc.  All rights reserved.   -->
<!-- ************************************************************************ -->

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
	<xsl:apply-templates select="cces-family-xml"/>
	</body>
	</html>
  </xsl:template> 

  <!-- ****************************************** -->
  <!-- ******   cces-family-xml      ******* -->
  <!-- ******     *-ALL-anomaly.xml       ******* -->
  <!-- ****************************************** -->

  <xsl:template match="cces-family-xml">

	<xsl:apply-templates select="anomaly-families"/>

  </xsl:template> 

  <!-- *************************** -->
  <!-- ******  Reference   ******* -->
  <!-- *************************** -->

  <xsl:template match="anomaly-families">

	<P/><HR size="4"/>
	<a name="FAMILY">
	<h2>CrossCore Embedded Studio Tools Behavior for Hardware Anomalies</h2>
	<xsl:if test="string-length(@family-name) &gt; 1">
		<h3><xsl:value-of select="@family-name"/> Family</h3>
	</xsl:if>
	</a>

	<xsl:if test="string(@verbose-display)='YES'">
		<xsl:text>
		For a description of the behavior of all tools in response to applicable anomalies, select the box.
		</xsl:text>
		<br></br><br></br>
		<xsl:text>
		For verbose assembler and compiler behavior per part and silicon revision, select from the list beneath the box.
		</xsl:text>
	</xsl:if>
	<br></br>

	<xsl:for-each select="family">
		<br></br>
		<table border="2" bordercolor="black" width="20%" cellpadding="6" cellspacing="0">
		<thead bgcolor="#efd6bc">
		<tr>
	       	<th width="20%" align="center" valign="center"><b><big>
		<a><xsl:attribute name="href"><xsl:value-of select="@xml-file"/></xsl:attribute><xsl:value-of select="@help-title"/></a>
			</big></b></th>
		</tr>
		</thead>
		</table><br></br>
			<xsl:for-each select="sub-family">
				<xsl:for-each select="processor">
				<a><xsl:attribute name="href"><xsl:value-of select="@xml-file"/></xsl:attribute><xsl:value-of select="@help-title"/></a>
				<xsl:text>&#160;&#160;&#160;</xsl:text>
				</xsl:for-each>
				<br></br><br></br>
			</xsl:for-each>
	</xsl:for-each>

  </xsl:template> 

  <xsl:template match="unused">

	<!-- ********************************* -->
	<!-- *******    Main menu      ******* -->
	<!-- ********************************* -->

	<br></br>
	<br></br>
	<table border="1" bgcolor="#cccccc" width="50%" cellpadding="6" cellspacing="6">

	<tr align="center">
		<th colspan="2"><b><big><a href="#COMPILER_ONLY">Compiler [verbose]</a></big></b></th>
	</tr>
	<tr align="center">
		<th colspan="2"><b><big><a href="#ASSEMBLER_ONLY">Assembler [verbose]</a></big></b></th>
	</tr>
	</table>

  </xsl:template> 

</xsl:stylesheet>
